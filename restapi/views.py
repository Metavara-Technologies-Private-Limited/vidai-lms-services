# =====================================================
# Python Standard Library
# =====================================================
import logging
import traceback
import requests
import secrets
from datetime import datetime, timedelta
import time

# =====================================================
# Django Imports
# =====================================================
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.utils.html import strip_tags

# =====================================================
# Third-Party Imports (DRF + Swagger)
# =====================================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# =====================================================
# Project Imports - Models
# =====================================================
from restapi.models import (
    Clinic, Ticket, Employee, Document, LeadNote, TicketTimeline,
    CampaignSocialMediaConfig, Pipeline, PipelineStage, LeadEmail,
    TemplateMail, TemplateSMS, TemplateWhatsApp,
    TemplateWhatsAppDocument, TemplateMailDocument, TemplateSMSDocument,
    CampaignEmailConfig, TwilioMessage, TwilioCall,
    MarketingEvent,  # ← ADDED: needed for CampaignMailchimpInsightsAPIView + MailchimpInsightsCallbackAPIView
)
from django.db.models import Count, Q  
from restapi.models import TicketReply
from restapi.models.social_account import SocialAccount
from restapi.services.ticket_service import send_ticket_reply_service
from .models import Lead, Campaign, Lab

# Reputation Management 
from django.shortcuts import get_object_or_404

# Reputation Management 
from restapi.models.reputation import ReviewRequest, Review
from restapi.serializers.reputation_serializer import (
    ReviewRequestSerializer,
    ReviewSerializer
)
from restapi.models.reputation import ReviewRequest, Review, ReviewRequestLead

# =====================================================
# Project Imports - Serializers
# =====================================================
from restapi.serializers.ticket_serializer import (
    TicketListSerializer, TicketDetailSerializer, TicketWriteSerializer,
    LabReadSerializer, LabWriteSerializer,
    TicketReplySerializer, TicketReplyWriteSerializer,
)
from restapi.serializers.clinic import ClinicSerializer, ClinicReadSerializer
from restapi.serializers.employee import (
    EmployeeCreateSerializer, EmployeeReadSerializer,
    UserCreateSerializer, EmployeeUpdateSerializer,
)
from restapi.serializers.lead_serializer import LeadSerializer, LeadReadSerializer
from restapi.serializers.lead_note_serializers import LeadNoteSerializer, LeadNoteReadSerializer
from restapi.serializers.lead_email_serializer import LeadEmailSerializer, LeadMailListSerializer
from restapi.serializers.campaign_serializer import (
    CampaignSerializer, CampaignReadSerializer,
    SocialMediaCampaignSerializer, EmailCampaignCreateSerializer,
)
from restapi.serializers.mailchimp_serializer import MailchimpWebhookSerializer
from restapi.serializers.campaign_social_post_serializer import CampaignSocialPostCallbackSerializer
from restapi.serializers.twilio_serializers import (
    SendSMSSerializer, MakeCallSerializer,
    TwilioMessageListSerializer, TwilioCallListSerializer,
)
from restapi.serializers.pipeline_serializer import PipelineSerializer, PipelineReadSerializer
from restapi.serializers.template_serializers import (
    TemplateMailSerializer, TemplateSMSSerializer, TemplateWhatsAppSerializer,
    TemplateMailReadSerializer, TemplateSMSReadSerializer, TemplateWhatsAppReadSerializer,
)

# =====================================================
# Project Imports - Services
# =====================================================
from restapi.services.lead_email_service import send_lead_email
from restapi.services.mailchimp_service import create_mailchimp_event
from restapi.services.mailchimp_service import (
    sync_contacts_to_mailchimp,
    create_and_send_mailchimp_campaign,
    get_mailchimp_campaign_report,
)
from restapi.services.campaign_social_post_service import handle_zapier_callback
from restapi.services.twilio_service import notify_zapier_event, send_sms, make_call
from restapi.services.zapier_service import (
    send_to_zapier,
    send_to_zapier_email,
    send_to_zapier_mailchimp_insights,  # ← ADDED
)

from restapi.services.pipeline_service import add_stage, update_stage, save_stage_rules, save_stage_fields
from restapi.services.lead_note_service import create_lead_note, update_lead_note, delete_lead_note

logger = logging.getLogger(__name__)

# =====================================================
# HELPERS
# =====================================================
_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.tiff', '.bmp')


def _is_direct_image_url(url: str) -> bool:
    """Return True when the URL is likely a direct image."""
    if not url:
        return False
    clean = url.split("?")[0].split("#")[0].lower()
    if clean.endswith(_IMAGE_EXTENSIONS):
        return True
    _IMAGE_CDN_HOSTS = (
        "images.unsplash.com", "images.pexels.com", "i.imgur.com",
        "res.cloudinary.com", "cdn.pixabay.com", "media.istockphoto.com",
        "images.squarespace-cdn.com", "cdn.shopify.com",
        "storage.googleapis.com", "s3.amazonaws.com",
    )
    try:
        import urllib.parse
        host = urllib.parse.urlparse(url).netloc.lower()
        return any(host == cdn or host.endswith("." + cdn) for cdn in _IMAGE_CDN_HOSTS)
    except Exception:
        return False


def _download_image(image_url: str):
    """
    Download image bytes from a public URL.
    Returns (image_bytes, filename, content_type) or (None, None, None).
    """
    import re
    import urllib.parse

    if not _is_direct_image_url(image_url):
        print(f"Skipping non-image URL: {image_url}")
        return None, None, None

    wiki_upload_pattern = re.compile(
        r"https://upload\.wikimedia\.org/wikipedia/(?:commons|en)/"
        r"(?:thumb/[^/]+/[^/]+/|[^/]+/[^/]+/)([^/?#]+?)(?:/\d+px-[^/?#]+)?(?:[?#].*)?$",
        re.IGNORECASE,
    )
    wiki_match = wiki_upload_pattern.match(image_url)
    if wiki_match:
        import hashlib
        raw_filename = urllib.parse.unquote(wiki_match.group(1))
        clean_filename = re.sub(r"^\d+px-", "", raw_filename).replace(" ", "_")
        if clean_filename:
            clean_filename = clean_filename[0].upper() + clean_filename[1:]
        md5 = hashlib.md5(clean_filename.encode("utf-8")).hexdigest()
        md5_url = (
            f"https://upload.wikimedia.org/wikipedia/commons/"
            f"{md5[0]}/{md5[:2]}/{urllib.parse.quote(clean_filename, safe='')}"
        )
        print(f"Wikipedia URL detected. Filename: {clean_filename}, MD5 URL: {md5_url}")
        try:
            head = requests.head(md5_url, timeout=8, allow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; LMS-Bot/1.0)"})
            if head.status_code == 200:
                image_url = md5_url
            else:
                api_url = (
                    "https://commons.wikimedia.org/w/api.php"
                    f"?action=query&titles=File:{urllib.parse.quote(clean_filename)}"
                    "&prop=imageinfo&iiprop=url&format=json&redirects=1"
                )
                api_resp = requests.get(api_url, timeout=10,
                                        headers={"User-Agent": "Mozilla/5.0 (compatible; LMS-Bot/1.0)"})
                pages = api_resp.json().get("query", {}).get("pages", {})
                resolved_url = None
                for page_id, page in pages.items():
                    if page_id != "-1":
                        imageinfo = page.get("imageinfo", [])
                        if imageinfo:
                            resolved_url = imageinfo[0].get("url")
                            break
                if resolved_url:
                    image_url = resolved_url
                else:
                    return None, None, None
        except Exception as wiki_err:
            print(f"Wikipedia check failed: {wiki_err}. Trying MD5 URL.")
            image_url = md5_url

    import urllib.parse as _up
    parsed = _up.urlparse(image_url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "sec-fetch-dest": "image",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "cross-site",
    }
    try:
        resp = requests.get(image_url, timeout=20, headers=headers, allow_redirects=True)
        print(f"Image download status: {resp.status_code} from {image_url}")
        if resp.status_code != 200:
            return None, None, None
        image_bytes = resp.content
        raw_filename = image_url.split("?")[0].split("/")[-1]
        image_filename = _up.unquote(raw_filename) or "image.jpg"
        image_filename = re.sub(r"\s+", "_", image_filename)
        ext = image_filename.split(".")[-1].lower()
        content_type_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "tiff": "image/tiff", "bmp": "image/bmp",
        }
        content_type = content_type_map.get(ext, "image/jpeg")
        print(f"Image: {image_filename} | {len(image_bytes)} bytes | {content_type}")
        return image_bytes, image_filename, content_type
    except Exception as e:
        print(f"Failed to download image: {e}")
        return None, None, None

# =====================================================
# FACEBOOK POST HELPER
# =====================================================
def post_to_facebook(page_id, page_token, message, image_url=None):
    """Post a message (with optional image) to a Facebook Page."""
    print("=" * 60)
    print("FACEBOOK POST DEBUG")
    print(f"Page ID    : {page_id}")
    print(f"Token (20) : {page_token[:20] if page_token else 'NONE'}")
    print(f"Message    : {message}")
    print(f"Image URL  : {image_url}")
    print("=" * 60)

    if image_url:
        image_bytes, image_filename, content_type = _download_image(image_url)
        if image_bytes:
            url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
            print(f"Posting WITH image to: {url}")
            response = requests.post(
                url,
                data={"caption": message, "access_token": page_token},
                files={"source": (image_filename, image_bytes, content_type)},
            )
        else:
            print("Image download failed. Falling back to text-only post.")
            image_url = None

    if not image_url:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        print(f"Posting TEXT-ONLY to: {url}")
        response = requests.post(url, data={"message": message, "access_token": page_token})

    print(f"HTTP Status : {response.status_code}")
    print(f"Response    : {response.text}")
    try:
        result = response.json()
    except Exception:
        return {}
    if "id" in result:
        print(f"Facebook Post ID: {result['id']}")
    else:
        print(f"Facebook Post Failed: {result.get('error', result)}")
    print("=" * 60)
    return result


def create_instagram_media(ig_user_id, access_token, image_url, caption):
    url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload)
    return response.json()


def publish_instagram_media(ig_user_id, access_token, creation_id):
    url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload)
    return response.json()


def post_to_instagram(ig_user_id, access_token, message, image_url):
    print("POSTING TO INSTAGRAM")
    media = create_instagram_media(ig_user_id, access_token, image_url, message)
    creation_id = media.get("id")
    if not creation_id:
        print("Failed to create media:", media)
        return media
    publish = publish_instagram_media(ig_user_id, access_token, creation_id)
    print("Instagram publish response:", publish)
    return publish


def post_to_linkedin(access_token, author_urn, message, image_url=None):
    print("=" * 60)
    print("LINKEDIN POST DEBUG")
    print("Author URN:", author_urn)
    print("Message:", message)
    print("Image URL:", image_url)
    print("=" * 60)

    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": message},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    response = requests.post(url, headers=headers, json=payload)
    print("LinkedIn Status:", response.status_code)
    print("LinkedIn Response:", response.text)
    try:
        return response.json()
    except Exception:
        return {}


# =====================================================
# MAIL NOTIFICATION HELPERS
# =====================================================
def _send_lead_created_mail(lead):
    """Send internal notification email when a new lead is created."""
    try:
        send_mail(
            subject=f"Lead Created - {lead.full_name}",
            message=(
                f"New lead has been created in the system.\n\n"
                f"Name    : {lead.full_name}\n"
                f"Contact : {lead.contact_no}\n"
                f"Email   : {lead.email}\n"
                f"Status  : {lead.lead_status}\n"
                f"Lead ID : {lead.id}\n"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=True,
        )
        print(f"Lead Created mail sent for: {lead.full_name}")
    except Exception as e:
        print(f"Lead Created mail failed: {e}")


def _send_appointment_booked_mail(lead):
    """Send internal notification email when a lead status becomes Appointment."""
    try:
        send_mail(
            subject=f"Appointment Booked at Clinic - {lead.full_name}",
            message=(
                f"An appointment has been booked.\n\n"
                f"Patient Name : {lead.full_name}\n"
                f"Contact      : {lead.contact_no}\n"
                f"Email        : {lead.email}\n"
                f"Lead ID      : {lead.id}\n"
                f"Booked At    : {timezone.now().strftime('%d-%m-%Y %H:%M')}\n"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=True,
        )
        print(f"Appointment Booked mail sent for: {lead.full_name}")
    except Exception as e:
        print(f"Appointment Booked mail failed: {e}")


# -------------------------------------------------------------------
# Create Clinic (POST)
# -------------------------------------------------------------------
class ClinicCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new clinic with departments",
        request_body=ClinicSerializer,
        responses={
            201: ClinicReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        try:
            serializer = ClinicSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            clinic = serializer.save()

            return Response(
                ClinicReadSerializer(clinic).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Clinic validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Clinic Create Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Update Clinic (PUT)
# -------------------------------------------------------------------
class ClinicUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing clinic and its departments",
        request_body=ClinicSerializer,
        responses={
            200: ClinicReadSerializer,
            400: "Validation Error",
            404: "Clinic not found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id)

            serializer = ClinicSerializer(
                clinic,
                data=request.data
            )
            serializer.is_valid(raise_exception=True)

            updated_clinic = serializer.save()

            return Response(
                ClinicReadSerializer(updated_clinic).data,
                status=status.HTTP_200_OK,
            )

        except Clinic.DoesNotExist:
            logger.warning("Clinic not found")
            raise NotFound("Clinic not found")

        except ValidationError as ve:
            logger.warning(
                f"Clinic update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Clinic Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Get Clinic by ID (GET)
# -------------------------------------------------------------------
class GetClinicView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve clinic details with departments",
        responses={
            200: ClinicReadSerializer,
            404: "Clinic not found",
            500: "Internal Server Error",
        },
    )
    def get(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id)

            serializer = ClinicReadSerializer(clinic)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Clinic.DoesNotExist:
            raise NotFound("Clinic not found")

        except Exception:
            logger.error(
                "Unhandled Clinic Fetch Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class ClinicSearchAPIView(APIView):

    def get(self, request):
        name = request.query_params.get("name")

        if not name:
            return Response(
                {"error": "name query param required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clinics = Clinic.objects.filter(name__iexact=name)

        if not clinics.exists():
            return Response([], status=status.HTTP_200_OK)

        serializer = ClinicReadSerializer(clinics, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# -------------------------------------------------------------------
# User Create API View (POST)
# -------------------------------------------------------------------
class UserCreateAPIView(APIView):

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "username": user.username
            },
            status=status.HTTP_201_CREATED
        )

# -------------------------------------------------------------------
# Clinic Employees API View (GET)
# -------------------------------------------------------------------
class ClinicEmployeesAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Get Clinic Employees",
        operation_description="Retrieve all employees under a specific clinic",
        responses={
            200: EmployeeReadSerializer(many=True),
            401: "Unauthorized",
            404: "Clinic not found",
        },
        tags=["Clinic"]
    )
    def get(self, request, clinic_id):
        get_object_or_404(Clinic, id=clinic_id)
        employees = Employee.objects.filter(clinic_id=clinic_id)
        serializer = EmployeeReadSerializer(employees, many=True)
        return Response(serializer.data)

# -------------------------------------------------------------------
# Employee Create API View (POST)
# -------------------------------------------------------------------
class EmployeeCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Create Employee",
        operation_description="Create an employee under a clinic and department",
        request_body=EmployeeCreateSerializer,
        responses={
            201: EmployeeReadSerializer,
            400: "Validation Error",
            401: "Unauthorized"
        },
        tags=["Employee"]
    )
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            EmployeeReadSerializer(employee).data,
            status=status.HTTP_201_CREATED
        )

class EmployeeUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Update Employee",
        operation_description="Update an existing employee's details (email, contact, type, etc.)",
        request_body=EmployeeUpdateSerializer,
        responses={
            200: EmployeeReadSerializer,
            400: "Validation Error",
            404: "Employee not found",
        },
        tags=["Employee"]
    )
    def put(self, request, employee_id):
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeUpdateSerializer(
            employee,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_employee = serializer.save()

        return Response(
            EmployeeReadSerializer(updated_employee).data,
            status=status.HTTP_200_OK,
        )


# =====================================================
# CREATE LEAD NOTE API
# =====================================================
class LeadNoteCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new note for a Lead",
        request_body=LeadNoteSerializer,
        responses={
            201: LeadNoteReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        try:
            serializer = LeadNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            note = serializer.save()

            return Response(
                LeadNoteReadSerializer(note).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead Note Create validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead Note Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# UPDATE LEAD NOTE API
# =====================================================
class LeadNoteUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing Lead note",
        request_body=LeadNoteSerializer,
        responses={
            200: LeadNoteReadSerializer,
            400: "Validation Error",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def put(self, request, note_id):
        try:
            note_instance = LeadNote.objects.filter(
                id=note_id,
                is_deleted=False
            ).first()

            if not note_instance:
                return Response(
                    {"error": "Lead note not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = LeadNoteSerializer(
                note_instance,
                data=request.data,
                partial=True
            )

            serializer.is_valid(raise_exception=True)
            updated_note = serializer.save()

            return Response(
                LeadNoteReadSerializer(updated_note).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(
                f"Lead Note Update validation failed: {validation_error.detail}"
            )
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Lead Note Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# DELETE LEAD NOTE API (SOFT DELETE)
# =====================================================
class LeadNoteDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a Lead note",
        responses={
            200: "Deleted Successfully",
            404: "Not Found",
            500: "Internal Server Error",
        },
    )
    def delete(self, request, note_id):
        try:
            note_instance = LeadNote.objects.filter(
                id=note_id,
                is_deleted=False
            ).first()

            if not note_instance:
                return Response(
                    {"error": "Lead note not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            delete_lead_note(note_instance)

            return Response(
                {"message": "Lead note deleted successfully."},
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead Note Delete validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead Note Delete Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# LIST NOTES BY LEAD API
# =====================================================
class LeadNoteListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all notes for a specific Lead",
        responses={
            200: LeadNoteReadSerializer(many=True),
            500: "Internal Server Error",
        },
    )
    def get(self, request, lead_id):
        try:
            notes = LeadNote.objects.filter(
                lead_id=lead_id,
                is_deleted=False
            ).order_by("-created_at")

            serializer = LeadNoteReadSerializer(notes, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Lead Note List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Lead Create API View (POST)
# -------------------------------------------------------------------
class LeadCreateAPIView(APIView):
    """
    Create Lead API (Supports JSON + File Upload)
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Create a new lead",
        request_body=LeadSerializer,
        responses={
            201: LeadReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Leads"],
    )
    def post(self, request):
        print("STEP 1: LeadCreateAPIView HIT")

        try:
            print("STEP 2: Incoming request data:")
            print(request.data)

            serializer = LeadSerializer(
                data=request.data,
                context={"request": request},
            )

            print("STEP 3: Serializer initialized")

            serializer.is_valid(raise_exception=True)
            print("STEP 4: Serializer validated successfully")

            lead = serializer.save()
            print(f"STEP 5: Lead saved successfully | ID = {lead.id}")

            print("STEP 6: Sending data to Zapier")

            send_to_zapier({
                "event": "lead_created",
                "lead_id": str(lead.id),
                "clinic_id": lead.clinic.id,
                "campaign_id": str(lead.campaign.id) if lead.campaign else None,
                "full_name": lead.full_name,
                "contact_no": lead.contact_no,
                "email": lead.email,
                "lead_status": lead.lead_status,
                "assigned_to_id": lead.assigned_to_id,
                
            })

            print("STEP 7: Zapier call completed")

            response_data = LeadReadSerializer(lead).data
            print("STEP 8: Response prepared")

            return Response(
                response_data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            print("VALIDATION ERROR OCCURRED")
            print(ve.detail)

            logger.warning(f"Lead validation failed: {ve.detail}")

            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            print("UNHANDLED EXCEPTION OCCURRED")
            print(traceback.format_exc())

            logger.error(
                "Unhandled Lead Create Error:\n" + traceback.format_exc()
            )

            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Lead Update API View (PUT)
# -------------------------------------------------------------------
class LeadUpdateAPIView(APIView):
    """
    Update an existing Lead
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(
        operation_description="Update an existing lead",
        request_body=LeadSerializer,
        responses={
            200: LeadReadSerializer,
            400: "Validation Error",
            404: "Lead not found",
            500: "Internal Server Error",
        },
        tags=["Leads"],
    )
    def put(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)

            serializer = LeadSerializer(
                lead,
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)

            updated_lead = serializer.save()

            send_to_zapier({
                "event": "lead_updated",
                "lead_id": str(updated_lead.id),
                "lead_status": updated_lead.lead_status,
                "assigned_to_id": updated_lead.assigned_to_id,
                
            })

            return Response(
                LeadReadSerializer(updated_lead).data,
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            logger.warning("Lead not found")
            raise NotFound("Lead not found")

        except ValidationError as ve:
            logger.warning(
                f"Lead update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error(
                "Unhandled Lead Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------------------------------------------------------------------
# Lead List API View (GET)
# -------------------------------------------------------------------
class LeadListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get all active leads",
        responses={200: LeadReadSerializer(many=True)},
        tags=["Leads"]
    )
    def get(self, request):
        try:
            queryset = Lead.objects.filter(
                is_deleted=False
            ).order_by("-created_at")

            clinic_id = request.query_params.get("clinic")
            lead_status = request.query_params.get("lead_status")
            assigned_to = request.query_params.get("assigned_to")

            if clinic_id:
                queryset = queryset.filter(clinic_id=clinic_id)

            if lead_status:
                queryset = queryset.filter(lead_status=lead_status)

            if assigned_to:
                queryset = queryset.filter(assigned_to_id=assigned_to)

            serializer = LeadReadSerializer(queryset, many=True)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        except ValidationError as validation_error:
            logger.warning(f"Lead list validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Lead List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Lead List API using ID (GET)
# -------------------------------------------------------------------
class LeadGetAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get lead by ID",
        responses={200: LeadReadSerializer, 404: "Lead not found"},
        tags=["Leads"]
    )
    def get(self, request, lead_id):
        lead = get_object_or_404(
            Lead.objects.select_related(
                "clinic",
                "department",
                "campaign",
                
            ),
            id=lead_id
        )

        return Response(
            LeadReadSerializer(lead).data,
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------------------
# Lead Activate API (Post)
# -------------------------------------------------------------------
class LeadActivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Activate a lead",
        tags=["Leads"]
    )
    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)

            lead.is_active = True
            lead.save(update_fields=["is_active"])

            return Response(
                {"message": "Lead activated successfully"},
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

# -------------------------------------------------------------------
# Lead In_Activate API (Patch)
# -------------------------------------------------------------------
class LeadInactivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Inactivate a lead",
        tags=["Leads"]
    )
    def patch(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)

            lead.is_active = False
            lead.save(update_fields=["is_active"])

            return Response(
                {"message": "Lead inactivated successfully"},
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

# -------------------------------------------------------------------
# Lead Soft Delete (Patch)
# -------------------------------------------------------------------
class LeadSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a lead",
        tags=["Leads"]
    )
    def patch(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)

            lead.is_deleted = True
            lead.is_active = False
            lead.save(update_fields=["is_deleted", "is_active"])

            return Response(
                {"message": "Lead soft deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Lead.DoesNotExist:
            raise NotFound("Lead not found")

    def delete(self, request, lead_id):
        return self.patch(request, lead_id)

# -------------------------------------------------------------------
# Lead Email API View (POST)
# -------------------------------------------------------------------
class LeadEmailAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Create Lead Email (Optional: Send Immediately)",
        operation_description="""
        Create an email record for a lead.

        If `send_now=true`, the email will be sent immediately.
        Otherwise, it will be saved as DRAFT.
        """,
        request_body=LeadEmailSerializer,
        responses={
            201: openapi.Response(
                description="Email created (and optionally sent)",
                schema=LeadEmailSerializer
            ),
            400: "Bad Request"
        }
    )
    @transaction.atomic
    def post(self, request):

        serializer = LeadEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        send_now = request.data.get("send_now", False)

        email_obj = serializer.save()

        if send_now:
            try:
                email_obj = send_lead_email(email_obj.id)

                return Response(
                    {
                        "message": "Email created and sent successfully",
                        "status": email_obj.status,
                        "sent_at": email_obj.sent_at,
                        "data": LeadEmailSerializer(email_obj).data
                    },
                    status=status.HTTP_201_CREATED
                )

            except Exception as e:
                return Response(
                    {
                        "message": "Email created but sending failed",
                        "error": str(e)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {
                "message": "Email saved as draft",
                "status": email_obj.status,
                "data": LeadEmailSerializer(email_obj).data
            },
            status=status.HTTP_201_CREATED
        )


class LeadMailListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve Lead Mail list (optional filter by lead_uuid)",
        manual_parameters=[
            openapi.Parameter(
                "lead_uuid",
                openapi.IN_QUERY,
                description="Filter by Lead UUID (optional)",
                type=openapi.TYPE_STRING,
                required=False,
            )
        ],
        responses={200: LeadMailListSerializer(many=True)},
        tags=["Lead Mail"],
    )
    def get(self, request):
        try:
            lead_uuid = request.query_params.get("lead_uuid")

            queryset = LeadEmail.objects.all().order_by("-created_at")

            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            serializer = LeadMailListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Lead Mail Fetch Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Campaign Create API View (POST)
# -------------------------------------------------------------------
class CampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description=(
            "Create a new campaign along with optional "
            "social media and email configurations"
        ),
        request_body=CampaignSerializer,
        responses={
            201: CampaignReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Campaigns"],
    )
    def post(self, request):
        try:
            serializer = CampaignSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            campaign = serializer.save()

            channels = []

            if campaign.social_configs.filter(is_active=True).exists():
                channels.append("facebook")

            if campaign.email_configs.filter(is_active=True).exists():
                channels.append("email")

            send_to_zapier({
                "event": "campaign_created",
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.campaign_name,
                "clinic_id": campaign.clinic.id,
                "campaign_mode": campaign.campaign_mode,
                "status": campaign.status,
                "is_active": campaign.is_active,
                "channels": channels,
                "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                "selected_start": campaign.selected_start.isoformat() if campaign.selected_start else None,
                "selected_end": campaign.selected_end.isoformat() if campaign.selected_end else None,
                "enter_time": campaign.enter_time.strftime("%H:%M") if campaign.enter_time else None,
            })

            return Response(
                CampaignReadSerializer(campaign).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Campaign validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Campaign Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Campaign Update API View (PUT)
# -------------------------------------------------------------------
class CampaignUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing campaign",
        request_body=CampaignSerializer,
        responses={
            200: CampaignReadSerializer,
            400: "Validation Error",
            404: "Campaign not found",
            500: "Internal Server Error",
        },
        tags=["Campaigns"],
    )
    def put(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            serializer = CampaignSerializer(
                campaign,
                data=request.data
            )
            serializer.is_valid(raise_exception=True)

            updated_campaign = serializer.save()

            channels = []
            if updated_campaign.social_configs.filter(is_active=True).exists():
                channels.append("facebook")
            if updated_campaign.email_configs.filter(is_active=True).exists():
                channels.append("email")

            send_to_zapier({
                "event": "campaign_updated",
                "campaign_id": str(updated_campaign.id),
                "campaign_name": updated_campaign.campaign_name,
                "clinic_id": updated_campaign.clinic.id,
                "campaign_mode": updated_campaign.campaign_mode,
                "status": updated_campaign.status,
                "is_active": updated_campaign.is_active,
                "channels": channels,
                "start_date": updated_campaign.start_date.isoformat() if updated_campaign.start_date else None,
                "end_date": updated_campaign.end_date.isoformat() if updated_campaign.end_date else None,
                "selected_start": updated_campaign.selected_start.isoformat() if updated_campaign.selected_start else None,
                "selected_end": updated_campaign.selected_end.isoformat() if updated_campaign.selected_end else None,
                "enter_time": updated_campaign.enter_time.strftime("%H:%M") if updated_campaign.enter_time else None,
            })

            return Response(
                CampaignReadSerializer(updated_campaign).data,
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            logger.warning("Campaign not found")
            raise NotFound("Campaign not found")

        except ValidationError as ve:
            logger.warning(
                f"Campaign update validation failed: {ve.detail}"
            )
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.error(
                "Unhandled Campaign Update Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# -------------------------------------------------------------------
# Campaign List API View (GET)
# -------------------------------------------------------------------
class CampaignListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get all campaigns with lead count",
        responses={200: CampaignReadSerializer(many=True)},
        tags=["Campaigns"]
    )
    def get(self, request):
        campaigns = Campaign.objects.all().order_by("-created_at")

        data = []
        for campaign in campaigns:
            campaign_data = CampaignReadSerializer(campaign).data
            campaign_data["lead_generated"] = campaign.leads.count()

            if campaign.mailchimp_campaign_id:
                report = get_mailchimp_campaign_report(campaign.mailchimp_campaign_id)
                if report:
                    campaign_data["impressions"] = report["opens"]
                    campaign_data["clicks"] = report["clicks"]
                    campaign_data["emails_sent"] = report["emails_sent"]
                    campaign_data["bounces"] = report["bounces"]
                    campaign_data["unsubscribes"] = report["unsubscribes"]
                else:
                    # ✅ FALLBACK: use last saved insights from CampaignEmailConfig
                    # ── Reads from insights JSONField (single column approach) ──
                    # If insights is None (never synced), defaults to 0 for all fields.
                    email_config = campaign.email_configs.filter(is_active=True).first()
                    cached = email_config.insights if email_config else None

                    if cached and cached.get("emails_sent") is not None:
                        # ✅ Read all values from insights JSON column
                        campaign_data["impressions"]  = cached.get("opens", 0)
                        campaign_data["clicks"]       = cached.get("clicks", 0)
                        campaign_data["emails_sent"]  = cached.get("emails_sent", 0)
                        campaign_data["bounces"]      = cached.get("bounces", 0)
                        campaign_data["unsubscribes"] = cached.get("unsubscribes", 0)
                    else:
                        campaign_data["impressions"]  = 0
                        campaign_data["clicks"]       = 0
                        campaign_data["emails_sent"]  = 0
                        campaign_data["bounces"]      = 0
                        campaign_data["unsubscribes"] = 0
            else:
                campaign_data["impressions"]  = 0
                campaign_data["clicks"]       = 0
                campaign_data["emails_sent"]  = 0
                campaign_data["bounces"]      = 0
                campaign_data["unsubscribes"] = 0

            data.append(campaign_data)

        return Response(data, status=status.HTTP_200_OK)

# -------------------------------------------------------------------
# Campaign Get API View With ID (GET)
# -------------------------------------------------------------------
class CampaignGetAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get campaign by ID",
        responses={200: CampaignReadSerializer},
        tags=["Campaigns"]
    )
    def get(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id)

        data = CampaignReadSerializer(campaign).data
        data["lead_generated"] = campaign.leads.count()

        if campaign.mailchimp_campaign_id:
            report = get_mailchimp_campaign_report(campaign.mailchimp_campaign_id)
            if report:
                data["impressions"]     = report["opens"]
                data["clicks"]          = report["clicks"]
                data["emails_sent"]     = report["emails_sent"]
                data["bounces"]         = report["bounces"]
                data["unsubscribes"]    = report["unsubscribes"]
                data["conversion_rate"] = (
                    round((data["lead_generated"] / report["emails_sent"]) * 100, 2)
                    if report["emails_sent"] > 0
                    else 0
                )
            else:
                # ✅ FALLBACK: use last saved insights from CampaignEmailConfig
                # This means dashboard NEVER shows 0 if insights were fetched before.
                # ── Reads from insights JSONField (single column approach) ──
                # If insights is None (never synced), defaults to 0 for all fields.
                email_config = campaign.email_configs.filter(is_active=True).first()
                cached = email_config.insights if email_config else None

                if cached and cached.get("emails_sent") is not None:
                    # ✅ Read all values from insights JSON column
                    data["impressions"]        = cached.get("opens", 0)
                    data["clicks"]             = cached.get("clicks", 0)
                    data["emails_sent"]        = cached.get("emails_sent", 0)
                    data["bounces"]            = cached.get("bounces", 0)
                    data["unsubscribes"]       = cached.get("unsubscribes", 0)
                    data["open_rate"]          = cached.get("open_rate", 0)
                    data["click_rate"]         = cached.get("click_rate", 0)
                    data["last_open"]          = cached.get("last_open")
                    data["last_click"]         = cached.get("last_click")
                    data["insights_synced_at"] = cached.get("synced_at")
                    data["conversion_rate"]    = (
                        round((data["lead_generated"] / cached.get("emails_sent")) * 100, 2)
                        if cached.get("emails_sent", 0) > 0
                        else 0
                    )
                else:
                    data["impressions"]     = 0
                    data["clicks"]          = 0
                    data["emails_sent"]     = 0
                    data["bounces"]         = 0
                    data["unsubscribes"]    = 0
        else:
            data["impressions"]  = 0
            data["clicks"]       = 0
            data["emails_sent"]  = 0
            data["bounces"]      = 0
            data["unsubscribes"] = 0

        if campaign.post_id:
            social = SocialAccount.objects.filter(
                clinic=campaign.clinic, platform="facebook", is_active=True
            ).first()
            if social:
                fb = get_facebook_post_insights(campaign.post_id, social.access_token)
                data["fb_likes"]       = fb.get("likes", 0)
                data["fb_comments"]    = fb.get("comments", 0)
                data["fb_shares"]      = fb.get("shares", 0)
                data["fb_impressions"] = fb.get("impressions", 0)
                data["fb_reach"]       = fb.get("reach", 0)
                data["fb_clicks"]      = fb.get("clicks", 0)
            else:
                data["fb_likes"] = data["fb_comments"] = data["fb_shares"] = 0
                data["fb_impressions"] = data["fb_reach"] = data["fb_clicks"] = 0
        else:
            data["fb_likes"] = data["fb_comments"] = data["fb_shares"] = 0
            data["fb_impressions"] = data["fb_reach"] = data["fb_clicks"] = 0

        return Response(data, status=status.HTTP_200_OK)


class FacebookDebugAPIView(APIView):
    def get(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id)
        social = SocialAccount.objects.filter(
            clinic=campaign.clinic, platform="facebook", is_active=True
        ).first()

        if not social:
            return Response({"error": "No Facebook account"})

        post_id = campaign.post_id

        token_debug = requests.get(
            "https://graph.facebook.com/debug_token",
            params={
                "input_token": social.access_token,
                "access_token": f"{settings.FACEBOOK_CLIENT_ID}|{settings.FACEBOOK_CLIENT_SECRET}",
            },
        ).json()

        page_id = social.page_id
        full_post_id = f"{page_id}_{post_id}" if "_" not in str(post_id) else post_id

        basic_raw = requests.get(
            f"https://graph.facebook.com/v19.0/{post_id}",
            params={
                "fields": "id,likes.summary(true),comments.summary(true),shares",
                "access_token": social.access_token,
            },
        ).json()

        basic_full = requests.get(
            f"https://graph.facebook.com/v19.0/{full_post_id}",
            params={
                "fields": "id,likes.summary(true),comments.summary(true),shares",
                "access_token": social.access_token,
            },
        ).json()

        insights_full = requests.get(
            f"https://graph.facebook.com/v19.0/{full_post_id}/insights",
            params={
                "metric": "post_impressions_unique,post_engaged_users,post_clicks_unique",
                "access_token": social.access_token,
            },
        ).json()

        user_token = getattr(social, "user_token", None) or social.access_token
        me_accounts = requests.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": user_token},
        ).json()

        page_token = None
        for page in me_accounts.get("data", []):
            if page.get("id") == page_id:
                page_token = page.get("access_token")
                break

        basic_with_page_token = {}
        if page_token:
            basic_with_page_token = requests.get(
                f"https://graph.facebook.com/v19.0/{full_post_id}",
                params={
                    "fields": "id,likes.summary(true),comments.summary(true)",
                    "access_token": page_token,
                },
            ).json()

        return Response(
            {
                "post_id_raw": post_id,
                "post_id_full": full_post_id,
                "page_id": page_id,
                "token_scopes": token_debug.get("data", {}).get("scopes", []),
                "token_is_valid": token_debug.get("data", {}).get("is_valid"),
                "token_expires_at": token_debug.get("data", {}).get("expires_at"),
                "basic_raw_format": basic_raw,
                "basic_full_format": basic_full,
                "insights_full_format": insights_full,
                "me_accounts": me_accounts,
                "page_token_found": page_token is not None,
                "basic_with_page_token": basic_with_page_token,
            }
        )


# -------------------------------------------------------------------
# Campaign Activate API (Post)
# -------------------------------------------------------------------
class CampaignActivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Activate a campaign",
        tags=["Campaigns"]
    )
    def post(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            campaign.is_active = True
            campaign.save(update_fields=["is_active"])

            return Response(
                {"message": "Campaign activated successfully"},
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            raise NotFound("Campaign not found")

# -------------------------------------------------------------------
# Campaign In_Activate API (Patch)
# -------------------------------------------------------------------
class CampaignInactivateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Inactivate a campaign",
        tags=["Campaigns"]
    )
    def patch(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            campaign.is_active = False
            campaign.save(update_fields=["is_active"])

            return Response(
                {"message": "Campaign inactivated successfully"},
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            raise NotFound("Campaign not found")

# -------------------------------------------------------------------
# Campaign Soft Delete API (Patch)
# -------------------------------------------------------------------
class CampaignSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a campaign",
        tags=["Campaigns"]
    )
    def patch(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            campaign.is_deleted = True
            campaign.is_active = False
            campaign.save(update_fields=["is_deleted", "is_active"])

            return Response(
                {"message": "Campaign soft deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Campaign.DoesNotExist:
            raise NotFound("Campaign not found")

    def delete(self, request, campaign_id):
        return self.patch(request, campaign_id)


class CampaignZapierCallbackAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Zapier callback to update social post status",
        request_body=CampaignSocialPostCallbackSerializer,
        responses={
            200: "Campaign social post updated successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Campaigns"],
    )
    def post(self, request):
        try:
            serializer = CampaignSocialPostCallbackSerializer(
                data=request.data
            )

            if not serializer.is_valid():
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )

            social_post = handle_zapier_callback(
                serializer.validated_data
            )

            return Response(
                {
                    "message": "Campaign social post updated successfully",
                    "social_post_id": str(social_post.id),
                    "status": social_post.status,
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "exception_type": type(e).__name__,
                    "trace": traceback.format_exc()
                },
                status=status.HTTP_400_BAD_REQUEST
            )

# -------------------------------------------------------------------
# Pipeline Create API View (POST)
# -------------------------------------------------------------------
class PipelineCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new sales pipeline",
        request_body=PipelineSerializer,
        responses={
            201: PipelineReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Pipelines"],
    )
    def post(self, request):
        try:
            serializer = PipelineSerializer(
                data=request.data,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)

            pipeline = serializer.save()

            return Response(
                PipelineReadSerializer(pipeline).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            logger.warning(f"Pipeline validation failed: {ve.detail}")
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# LIST PIPELINES (GET)
# -------------------------------------------------------------------
class PipelineListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all pipelines for a clinic",
        responses={200: PipelineReadSerializer(many=True)},
        tags=["Pipelines"],
    )
    def get(self, request):
        try:
            clinic_id = request.query_params.get("clinic_id")
            if not clinic_id:
                raise ValidationError({"clinic_id": "This field is required"})

            pipelines = Pipeline.objects.filter(
                clinic_id=clinic_id,
                is_active=True
            )

            return Response(
                PipelineReadSerializer(pipelines, many=True).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline List Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# GET SINGLE PIPELINE (GET)
# -------------------------------------------------------------------
class PipelineDetailAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get pipeline with stages, rules, and fields",
        responses={200: PipelineReadSerializer},
        tags=["Pipelines"],
    )
    def get(self, request, pipeline_id):
        try:
            pipeline = Pipeline.objects.get(id=pipeline_id)

            return Response(
                PipelineReadSerializer(pipeline).data,
                status=status.HTTP_200_OK,
            )

        except Pipeline.DoesNotExist:
            return Response(
                {"error": "Pipeline not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception:
            logger.error(
                "Unhandled Pipeline Detail Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# ADD STAGE TO PIPELINE (POST)
# -------------------------------------------------------------------
class PipelineStageCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Add a new stage to a pipeline",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "pipeline_id": openapi.Schema(type=openapi.TYPE_STRING),
                "stage_name": openapi.Schema(type=openapi.TYPE_STRING),
                "stage_type": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=["pipeline_id", "stage_name", "stage_type"],
        ),
        tags=["Pipeline Stages"],
    )
    def post(self, request):
        try:
            stage = add_stage(request.data)

            return Response(
                {"id": stage.id, "stage_name": stage.stage_name},
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Create Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# UPDATE STAGE (PUT)
# -------------------------------------------------------------------
class PipelineStageUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update pipeline stage",
        tags=["Pipeline Stages"],
    )
    def put(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            update_stage(stage, request.data)

            return Response(
                {"message": "Stage updated successfully"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Update Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# SAVE STAGE RULES (POST)
# -------------------------------------------------------------------
class StageRuleSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage action rules",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            save_stage_rules(stage, request.data.get("rules", []))

            return Response(
                {"message": "Stage rules saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Rule Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# SAVE STAGE FIELDS (POST)
# -------------------------------------------------------------------
class StageFieldSaveAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Save stage data capture fields",
        tags=["Pipeline Stages"],
    )
    def post(self, request, stage_id):
        try:
            stage = PipelineStage.objects.get(id=stage_id)
            save_stage_fields(stage, request.data.get("fields", []))

            return Response(
                {"message": "Stage fields saved"},
                status=status.HTTP_200_OK,
            )

        except PipelineStage.DoesNotExist:
            return Response(
                {"error": "Stage not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Unhandled Stage Field Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

CAMPAIGN_OBJECTIVES = {
    "awareness": "Brand Awareness",
    "leads": "Lead Generation",
}


class EmailCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Email Campaign Only",
        request_body=EmailCampaignCreateSerializer,
        responses={
            201: "Email Campaign Created Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Email Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = EmailCampaignCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            selected_start = data.get("selected_start")
            enter_time = data.get("enter_time")

            now = timezone.now()

            scheduled_datetime = None

            if not selected_start or not enter_time:
                campaign_status = "draft"
                is_active_value = False
            else:
                scheduled_datetime = timezone.make_aware(
                    datetime.combine(selected_start, enter_time)
                )

                if scheduled_datetime > now:
                    campaign_status = "scheduled"
                    is_active_value = True
                else:
                    campaign_status = "live"
                    is_active_value = True

            campaign = Campaign.objects.create(
                clinic_id=data["clinic"],
                campaign_name=data["campaign_name"],
                campaign_description=data["campaign_description"],
                campaign_objective=data["campaign_objective"],
                target_audience=data["target_audience"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                campaign_mode=Campaign.EMAIL,
                selected_start=data.get("selected_start"),
                selected_end=data.get("selected_end"),
                enter_time=data.get("enter_time"),
                status=campaign_status,
                is_active=is_active_value,
            )

            emails = list(
                Lead.objects.filter(clinic=campaign.clinic, email__isnull=False)
                .exclude(email="")
                .values_list("email", flat=True)
            )

            created_email_configs = []

            for email_data in data["email"]:
                email_config = CampaignEmailConfig.objects.create(
                    campaign=campaign,
                    audience_name=email_data["audience_name"],
                    subject=email_data["subject"],
                    email_body=email_data["email_body"],
                    template_name=email_data.get("template_name"),
                    sender_email=email_data["sender_email"],
                    scheduled_at=scheduled_datetime,
                    is_active=True,
                )

                sync_contacts_to_mailchimp(emails)

                mailchimp_id = create_and_send_mailchimp_campaign(
                    campaign_id=str(campaign.id),
                    subject=email_config.subject,
                    email_body=email_config.email_body,
                    sender_email=email_config.sender_email,
                    campaign_name=campaign.campaign_name,
                    scheduled_at=scheduled_datetime,
                )

                # 3. Save mailchimp_campaign_id on campaign for later metric fetching
                campaign.mailchimp_campaign_id = mailchimp_id
                campaign.save(update_fields=["mailchimp_campaign_id"])

                # ---------------------------------------------------------
                # FUTURE: Fetch template attachments and send file URLs
                # ---------------------------------------------------------
                attachments = []

                # Uncomment later when template attachments are enabled
                # try:
                #     from restapi.models import TemplateMailDocument  # adjust import
                #
                #     template_docs = TemplateMailDocument.objects.filter(
                #         template__name=email_config.template_name
                #     )
                #
                #     for doc in template_docs:
                #         attachments.append({
                #             "file_url": request.build_absolute_uri(doc.file.url),
                #             "file_name": doc.file.name.split("/")[-1],
                #         })
                #
                # except Exception:
                #     logger.warning("Failed to fetch template attachments")
                # ---------------------------------------------------------

                # ── Send email campaign data to dedicated Email Zapier webhook ──
                # Uses send_to_zapier_email → ZAPIER_WEBHOOK_EMAIL_URL
                # (NOT the generic ZAPIER_WEBHOOK_URL used for leads/social campaigns)
                send_to_zapier_email(
                    {
                        "event": "email_campaign_created",
                        "emails": emails,
                        "campaign_id": str(campaign.id),
                        "campaign_name": campaign.campaign_name,
                        "campaign_description": campaign.campaign_description,
                        "campaign_objective": CAMPAIGN_OBJECTIVES.get(
                            campaign.campaign_objective
                        ),
                        "target_audience": campaign.target_audience,
                        "start_date": campaign.start_date.isoformat(),
                        "end_date": campaign.end_date.isoformat(),
                        "subject": email_config.subject,
                        "email_body": email_config.email_body,
                        "sender_email": email_config.sender_email,
                        "scheduled_at": (
                            email_config.scheduled_at.isoformat()
                            if email_config.scheduled_at
                            else None
                        ),
                        # "attachments": attachments
                    }
                )

                created_email_configs.append(
                    {
                        "email_config_id": email_config.id,
                        "audience_name": email_config.audience_name,
                    }
                )

            return Response(
                {
                    "message": "Email campaign created successfully",
                    "campaign_id": campaign.id,
                    "emails": created_email_configs,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Email Campaign Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Mailchimp Webhook Receiver API View (POST)
# -------------------------------------------------------------------
class MailchimpWebhookAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Mailchimp Webhook Receiver",
        request_body=MailchimpWebhookSerializer,
        responses={
            200: "Mailchimp Event Stored Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Mailchimp"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = MailchimpWebhookSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            create_mailchimp_event(validated_data)

            return Response(
                {"message": "Mailchimp event stored successfully"},
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Mailchimp Webhook Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# SEND SMS API
# -------------------------------------------------------------------
class SendSMSAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Send SMS using Twilio",
        request_body=SendSMSSerializer,
        responses={
            200: "SMS Sent Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = SendSMSSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            message = send_sms(
                lead_uuid=validated_data["lead_uuid"],
                to_number=validated_data["to"],
                message_body=validated_data["message"]
            )

            return Response(
                {
                    "message": "SMS sent successfully",
                    "sid": message.sid,
                    "status": message.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio SMS Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# MAKE CALL API
# -------------------------------------------------------------------
class MakeCallAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Make outbound call using Twilio",
        request_body=MakeCallSerializer,
        responses={
            200: "Call Initiated Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = MakeCallSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            call = make_call(
                lead_uuid=validated_data["lead_uuid"],
                to_number=validated_data["to"]
            )

            return Response(
                {
                    "message": "Call initiated successfully",
                    "sid": call.sid,
                    "status": call.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio Call Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# SEND SMS API
# -------------------------------------------------------------------
class SendSMSAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Send SMS using Twilio",
        request_body=SendSMSSerializer,
        responses={
            200: "SMS Sent Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            logger.info(
                "SendSMSAPIView request received: payload_keys=%s",
                list(request.data.keys()) if hasattr(request, "data") else [],
            )

            serializer = SendSMSSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            logger.info(
                "SendSMSAPIView hit: lead_uuid=%s to=%s",
                validated_data.get("lead_uuid"),
                validated_data.get("to"),
            )

            message = send_sms(
                lead_uuid=validated_data["lead_uuid"],
                to_number=validated_data["to"],
                message_body=validated_data["message"]
            )

            logger.info(
                "SendSMSAPIView success: sid=%s status=%s",
                message.sid,
                message.status,
            )

            return Response(
                {
                    "message": "SMS sent successfully",
                    "sid": message.sid,
                    "status": message.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio SMS Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# MAKE CALL API
# -------------------------------------------------------------------
class MakeCallAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Make outbound call using Twilio",
        request_body=MakeCallSerializer,
        responses={
            200: "Call Initiated Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            logger.info(
                "MakeCallAPIView request received: payload_keys=%s",
                list(request.data.keys()) if hasattr(request, "data") else [],
            )

            serializer = MakeCallSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            logger.info(
                "MakeCallAPIView hit: lead_uuid=%s to=%s",
                validated_data.get("lead_uuid"),
                validated_data.get("to"),
            )

            call = make_call(
                lead_uuid=validated_data["lead_uuid"],
                to_number=validated_data["to"]
            )

            logger.info(
                "MakeCallAPIView success: sid=%s status=%s",
                call.sid,
                call.status,
            )

            return Response(
                {
                    "message": "Call initiated successfully",
                    "sid": call.sid,
                    "status": call.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio Call Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TwilioSMSStatusCallbackAPIView(APIView):
    """Receives Twilio SMS status callbacks and forwards updates to Zapier."""

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request):
        try:
            payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)

            sid = payload.get("MessageSid") or payload.get("SmsSid")
            message_status = payload.get("MessageStatus") or payload.get("SmsStatus")
            to_number = payload.get("To")
            from_number = payload.get("From")
            error_code = payload.get("ErrorCode")
            error_message = payload.get("ErrorMessage")

            logger.info(
                "TwilioSMSStatusCallback received: sid=%s status=%s to=%s from=%s",
                sid,
                message_status,
                to_number,
                from_number,
            )

            twilio_message = (
                TwilioMessage.objects.select_related("lead")
                .filter(sid=sid)
                .first()
                if sid
                else None
            )

            lead_uuid = None
            if twilio_message:
                lead_uuid = str(twilio_message.lead_id) if twilio_message.lead_id else None
                merged_payload = twilio_message.raw_payload if isinstance(twilio_message.raw_payload, dict) else {}
                merged_payload["sms_status_callback"] = payload
                merged_payload["last_status_callback_at"] = timezone.now().isoformat()

                if message_status:
                    twilio_message.status = message_status
                twilio_message.raw_payload = merged_payload
                twilio_message.save(update_fields=["status", "raw_payload"])
            else:
                logger.warning("TwilioSMSStatusCallback SID not found in DB: sid=%s", sid)

            notify_zapier_event("sms_status_updated", {
                "lead_uuid": lead_uuid,
                "sid": sid,
                "status": message_status,
                "to_number": to_number,
                "from_number": from_number,
                "error_code": error_code,
                "error_message": error_message,
            })

            return Response({"message": "SMS callback processed"}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio SMS Callback Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwilioCallStatusCallbackAPIView(APIView):
    """Receives Twilio call status callbacks and forwards updates to Zapier."""

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request):
        try:
            payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)

            sid = payload.get("CallSid")
            call_status = payload.get("CallStatus")
            to_number = payload.get("To")
            from_number = payload.get("From")
            direction = payload.get("Direction")

            logger.info(
                "TwilioCallStatusCallback received: sid=%s status=%s to=%s from=%s",
                sid,
                call_status,
                to_number,
                from_number,
            )

            twilio_call = (
                TwilioCall.objects.select_related("lead")
                .filter(sid=sid)
                .first()
                if sid
                else None
            )

            lead_uuid = None
            if twilio_call:
                lead_uuid = str(twilio_call.lead_id) if twilio_call.lead_id else None
                merged_payload = twilio_call.raw_payload if isinstance(twilio_call.raw_payload, dict) else {}
                merged_payload["call_status_callback"] = payload
                merged_payload["last_status_callback_at"] = timezone.now().isoformat()

                if call_status:
                    twilio_call.status = call_status
                twilio_call.raw_payload = merged_payload
                twilio_call.save(update_fields=["status", "raw_payload"])
            else:
                logger.warning("TwilioCallStatusCallback SID not found in DB: sid=%s", sid)

            notify_zapier_event("call_status_updated", {
                "lead_uuid": lead_uuid,
                "sid": sid,
                "status": call_status,
                "to_number": to_number,
                "from_number": from_number,
                "direction": direction,
            })

            return Response({"message": "Call callback processed"}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio Call Callback Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwilioMessageListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve SMS list",
        manual_parameters=[
            openapi.Parameter(
                "lead_uuid",
                openapi.IN_QUERY,
                description="Filter by Lead UUID",
                type=openapi.TYPE_STRING,
            )
        ],
        responses={200: TwilioMessageListSerializer(many=True)},
        tags=["Twilio"],
    )
    def get(self, request):
        try:
            lead_uuid = request.query_params.get("lead_uuid")

            queryset = TwilioMessage.objects.all()

            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            serializer = TwilioMessageListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio SMS Fetch Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TwilioCallListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve Call list",
        manual_parameters=[
            openapi.Parameter(
                "lead_uuid",
                openapi.IN_QUERY,
                description="Filter by Lead UUID",
                type=openapi.TYPE_STRING,
            )
        ],
        responses={200: TwilioCallListSerializer(many=True)},
        tags=["Twilio"],
    )
    def get(self, request):
        try:
            lead_uuid = request.query_params.get("lead_uuid")

            queryset = TwilioCall.objects.all()

            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            serializer = TwilioCallListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio Call Fetch Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



# -------------------------------------------------------------------
# Social Media Campaign Create API View (POST)
# -------------------------------------------------------------------
class SocialMediaCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Social Media Campaign Only",
        request_body=SocialMediaCampaignSerializer,
        responses={
            201: "Campaign Created Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Social Media Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            print("SOCIAL DATA:", request.data)
            serializer = SocialMediaCampaignSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data

            mode_mapping = {
                "organic_posting": Campaign.ORGANIC,
                "paid_advertising": Campaign.PAID,
            }

            created_campaigns = []

            for mode in data["campaign_mode"]:

                raw_platform_data = data.get("platform_data") or {}
                raw_campaign_content = (data.get("campaign_content") or "").strip()

                # Helper: extract first image URL from mixed text+URL string
                def _extract_image_url(text):
                    if not text:
                        return None, text
                    text = text.strip()
                    # Case 1: entire string is just a URL
                    if (
                        _is_direct_image_url(text)
                        and "\n" not in text
                        and " " not in text
                    ):
                        return text, ""
                    # Case 2: URL embedded inside text
                    tokens = text.replace("\n", " ").split()
                    for token in tokens:
                        token = token.strip(".,;!?\"'")
                        if _is_direct_image_url(token):
                            clean = text.replace(token, "").strip().strip(".,;!?\n ")
                            return token, clean
                    return None, text

                # Resolve facebook message text
                _platform_facebook = strip_tags(
                    raw_platform_data.get("facebook", "") or ""
                ).strip()
                _campaign_content = strip_tags(raw_campaign_content).strip()

                # Extract any embedded image URL from the text fields
                _fb_extracted_url, _platform_facebook = _extract_image_url(
                    _platform_facebook
                )
                _cc_extracted_url, _campaign_content = _extract_image_url(
                    _campaign_content
                )

                facebook_message = _platform_facebook or _campaign_content

                # Resolve image_url
                # Priority: 1. Explicit image_url field  2. platform_data.facebook  3. campaign_content
                _raw_image_url = (request.data.get("image_url") or "").strip()
                if _raw_image_url:
                    _extracted, _ = _extract_image_url(_raw_image_url)
                    image_url_field = _extracted or None
                    if image_url_field != _raw_image_url:
                        print(
                            f"image_url cleaned: {repr(_raw_image_url[:80])} -> {image_url_field}"
                        )
                else:
                    image_url_field = None

                if not image_url_field and _fb_extracted_url:
                    image_url_field = _fb_extracted_url
                    print(
                        f"image_url extracted from platform_data.facebook: {image_url_field}"
                    )

                if not image_url_field and _cc_extracted_url:
                    image_url_field = _cc_extracted_url
                    print(
                        f"image_url extracted from campaign_content: {image_url_field}"
                    )

                print("=" * 60)
                print("DEBUG raw platform_data   :", raw_platform_data)
                print("DEBUG campaign_content     :", _campaign_content)
                print("DEBUG facebook_message     :", facebook_message)
                print("DEBUG image_url            :", image_url_field)
                print("=" * 60)

                # Build selected_start / selected_end
                from datetime import datetime, time, date as date_type

                start = data["start_date"]
                end = data["end_date"]

                selected_start = timezone.make_aware(
                    datetime.combine(
                        (
                            start
                            if isinstance(start, date_type)
                            else datetime.strptime(start, "%Y-%m-%d").date()
                        ),
                        time(0, 0, 0),
                    )
                )
                selected_end = timezone.make_aware(
                    datetime.combine(
                        (
                            end
                            if isinstance(end, date_type)
                            else datetime.strptime(end, "%Y-%m-%d").date()
                        ),
                        time(23, 59, 59),
                    )
                )

                # =====================================================
                # FIX: Only store budget for SELECTED platforms
                # Previously: budget_data=data.get("budget_data") or {}
                # stored ALL platforms (instagram/facebook/linkedin)
                # even when only 2 were selected — causing wrong totals.
                # Now we filter to only the selected platforms + recompute total.
                # =====================================================
                selected_platforms = data["select_ad_accounts"]
                raw_budget_data = data.get("budget_data") or {}
                filtered_budget = {
                    p: raw_budget_data.get(p, 0) for p in selected_platforms
                }
                filtered_budget["total"] = sum(
                    v for k, v in filtered_budget.items() if k != "total"
                )

                campaign = Campaign.objects.create(
                    clinic_id=data["clinic"],
                    campaign_name=data["campaign_name"],
                    campaign_description=data["campaign_description"],
                    campaign_objective=data["campaign_objective"],
                    target_audience=data["target_audience"],
                    start_date=data["start_date"],
                    end_date=data["end_date"],
                    campaign_mode=mode_mapping.get(mode),
                    campaign_content=facebook_message,
                    selected_start=selected_start,
                    selected_end=selected_end,
                    enter_time=data["enter_time"],
                    platform_data=raw_platform_data,
                    budget_data=filtered_budget,
                    image_url=image_url_field,
                    is_active=True,
                )

                print("=" * 60)
                print("PLATFORM DATA:", campaign.platform_data)
                print("FACEBOOK MESSAGE:", facebook_message)
                print("IMAGE URL SAVED:", campaign.image_url)
                print("=" * 60)

                channels = []

                for platform in data["select_ad_accounts"]:
                    CampaignSocialMediaConfig.objects.create(
                        campaign=campaign,
                        platform_name=platform,
                        is_active=True,
                    )
                    channels.append(platform)

                clinic_id = data["clinic"]

                # social = SocialAccount.objects.filter(
                #     clinic_id=clinic_id,
                #     platform="facebook",
                #     is_active=True
                # ).first()

                # fb_post_id = None

                # print("=" * 60)
                # print("CHANNELS:", channels)
                # print("SOCIAL ACCOUNT FOUND:", social)
                # print("=" * 60)

                if "facebook" in channels:
                    # if not social:
                    #     print("NO FACEBOOK SOCIAL ACCOUNT for clinic_id:", clinic_id)
                    #     return Response(
                    #         {"error": "Facebook not connected for this clinic"},
                    #         status=400
                    #     )

                    if not facebook_message:
                        facebook_message = campaign.campaign_name

                    formatted_message = (
                        f"📢 {campaign.campaign_name}\n\n"
                        f"{facebook_message}\n\n"
                        f"📅 Campaign Duration: "
                        f"{campaign.start_date.strftime('%d %b %Y')} – "
                        f"{campaign.end_date.strftime('%d %b %Y')}\n"
                        f"⏰ Scheduled Time: "
                        f"{campaign.enter_time.strftime('%I:%M %p') if campaign.enter_time else 'N/A'}\n"
                        f"🎯 Objective: {campaign.campaign_objective}\n"
                        f"👥 Target Audience: {campaign.target_audience}\n\n"
                        f"#LMS #Campaign #{campaign.campaign_name.replace(' ', '')}"
                    )

                    fb_post_id = None

                    print("=" * 60)
                    print("CHANNELS:", channels)
                    print("FORMATTED MESSAGE:", formatted_message[:80], "...")
                    print("=" * 60)

                    if "facebook" in channels:
                        social_fb = SocialAccount.objects.filter(
                            clinic_id=clinic_id, platform="facebook", is_active=True
                        ).first()

                        if not social_fb:
                            print(
                                "NO FACEBOOK SOCIAL ACCOUNT for clinic_id:", clinic_id
                            )
                            return Response(
                                {"error": "Facebook not connected for this clinic"},
                                status=400,
                            )

                        print(">>> CALLING post_to_facebook()")
                        print("Page ID   :", social_fb.page_id)
                        print("Page Name :", social_fb.page_name)
                        print(
                            "Token (20):",
                            (
                                social_fb.access_token[:20]
                                if social_fb.access_token
                                else "NONE"
                            ),
                        )
                        print("Image URL :", campaign.image_url)

                        fb_response = post_to_facebook(
                            page_id=social_fb.page_id,
                            page_token=social_fb.access_token,
                            message=formatted_message,
                            image_url=campaign.image_url,
                        )

                        print("FB POST FULL RESPONSE:", fb_response)
                        # Use post_id (full page_post format) if available, else fall back to id
                        fb_post_id = fb_response.get("post_id") or fb_response.get("id")
                        print("FB POST ID:", fb_post_id)

                        if fb_post_id:
                            campaign.post_id = fb_post_id
                            campaign.save(update_fields=["post_id"])
                            print("FB POST ID SAVED:", fb_post_id)
                        else:
                            print("FB POST ID IS NONE — check FB error above")

                        # =====================================================
                        # CREATE FACEBOOK AD CAMPAIGN (Paid mode only)
                        # =====================================================
                        if "facebook" in channels:
                            try:
                                fb_budget = filtered_budget.get("facebook", 200)
                                fb_camp_r = requests.post(
                                    f"https://graph.facebook.com/v19.0/act_{settings.FB_AD_ACCOUNT_ID}/campaigns",
                                    data={
                                        "name": campaign.campaign_name,
                                        "objective": "OUTCOME_LEADS",
                                        "status": "PAUSED",
                                        "daily_budget": int(fb_budget) * 100,
                                        "special_ad_categories": "[]",
                                        "is_adset_budget_sharing_enabled": False,
                                        "access_token": settings.FB_ACCESS_TOKEN,
                                    }
                                )
                                fb_camp_data = fb_camp_r.json()
                                if "id" in fb_camp_data:
                                    campaign.fb_campaign_id = fb_camp_data["id"]
                                    campaign.save(update_fields=["fb_campaign_id"])
                                    print("FB AD CAMPAIGN CREATED:", fb_camp_data["id"])
                                else:
                                    print("FB AD CAMPAIGN ERROR:", fb_camp_data)
                            except Exception:
                                print("FB AD CAMPAIGN FAILED:\n" + traceback.format_exc())

                    if "instagram" in channels:
                        if not campaign.image_url:
                            print(
                                "Skipping Instagram: image_url is required for Instagram posts"
                            )
                        else:
                            social_ig = SocialAccount.objects.filter(
                                clinic_id=clinic_id, platform="facebook", is_active=True
                            ).first()

                            ig_user_id = getattr(social_ig, "instagram_id", None)

                            if not social_ig or not ig_user_id:
                                print(
                                    "Instagram not connected or instagram_id missing on SocialAccount"
                                )
                            else:
                                print(">>> CALLING post_to_instagram()")
                                print("IG User ID :", ig_user_id)
                                ig_response = post_to_instagram(
                                    ig_user_id=ig_user_id,
                                    access_token=social_ig.access_token,
                                    message=formatted_message,
                                    image_url=campaign.image_url,
                                )
                                print("IG POST RESPONSE:", ig_response)

                    if "linkedin" in channels:
                        social_li = SocialAccount.objects.filter(
                            clinic_id=clinic_id, platform="linkedin", is_active=True
                        ).first()

                        if not social_li:
                            print("LinkedIn not connected for clinic_id:", clinic_id)
                        else:
                            print(">>> CALLING post_to_linkedin()")
                            print("Author URN :", social_li.linkedin_urn)
                            li_response = post_to_linkedin(
                                access_token=social_li.linkedin_token,
                                author_urn=social_li.linkedin_urn,
                                message=formatted_message,
                                image_url=campaign.image_url,
                            )
                            print("LI POST RESPONSE:", li_response)

                created_campaigns.append(
    {
        "campaign_id": str(campaign.id),
        "mode": mode,
        "platforms": channels,
        "fb_post_id": fb_post_id,
        "fb_campaign_id": campaign.fb_campaign_id,
    }
)

            return Response(
                {
                    "message": "Social media campaign(s) created successfully",
                    "campaigns": created_campaigns,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "type": type(e).__name__,
                    "trace": traceback.format_exc(),
                },
                status=400,
            )


def get_facebook_post_insights(post_id, page_token):
    print("=" * 60)
    print("FB INSIGHTS: post_id =", post_id)

    result = {
        "post_id": post_id,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "impressions": 0,
        "reach": 0,
        "clicks": 0,
        "pending_review": True,
    }

    try:
        basic_url = f"https://graph.facebook.com/v19.0/{post_id}"
        basic_params = {
            "fields": "likes.summary(true),comments.summary(true)",
            "access_token": page_token,
        }
        basic_resp = requests.get(basic_url, params=basic_params, timeout=10)
        print("BASIC STATUS:", basic_resp.status_code, basic_resp.text[:200])

        if basic_resp.status_code == 200:
            basic_data = basic_resp.json()
            result["likes"] = (
                basic_data.get("likes", {}).get("summary", {}).get("total_count", 0)
            )
            result["comments"] = (
                basic_data.get("comments", {}).get("summary", {}).get("total_count", 0)
            )
            result["pending_review"] = False
    except Exception as e:
        print(f"FB insights fetch failed: {e}")

    print("FB INSIGHTS RESULT:", result)
    print("=" * 60)
    return result


def list_available_metrics(post_id, page_token):
    print("🚀 list_available_metrics CALLED")

    candidates = [
        "post_impressions",
        "post_impressions_unique",
        "post_engaged_users",
        "post_clicks",
        "post_reactions_by_type",
        "post_video_views",
        "post_video_complete_views_organic",
        "post_activity",
        "post_activity_unique",
    ]

    results = {}
    for metric in candidates:
        print(f"🔍 Testing metric: {metric}")
        url = f"https://graph.facebook.com/v19.0/{post_id}/insights"
        try:
            r = requests.get(
                url, params={"metric": metric, "access_token": page_token}, timeout=10
            )
            print(f"   Status: {r.status_code}")
            if r.status_code == 200:
                results[metric] = "✅ OK"
            else:
                error_msg = r.json().get("error", {}).get("message", "unknown error")
                results[metric] = f"❌ {error_msg}"
        except Exception as e:
            print(f"   EXCEPTION: {e}")
            results[metric] = f"💥 Exception: {str(e)}"

    print("✅ list_available_metrics DONE:", results)
    return results


class CampaignFacebookInsightsAPIView(APIView):
    def get(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id)

        if not campaign.post_id:
            return Response({"error": "Campaign has no Facebook post"}, status=400)

        social = SocialAccount.objects.filter(
            clinic=campaign.clinic, platform="facebook", is_active=True
        ).first()

        if not social:
            return Response({"error": "Facebook not connected"}, status=400)

        token = social.access_token
        print("🔑 Using token:", token[:30] if token else "NONE")

        insights = get_facebook_post_insights(campaign.post_id, token)
        return Response({"post_id": campaign.post_id, "insights": insights})


# =====================================================
# NEW: CAMPAIGN MAILCHIMP INSIGHTS API (GET via Zapier)
# GET /api/campaigns/<campaign_id>/mailchimp-insights/
#
# Flow:
#   1. FE calls GET /api/campaigns/<id>/mailchimp-insights/
#   2. BE fetches directly from Mailchimp API (fast, immediate result)
#   3. ✅ Saves insights to CampaignEmailConfig.insights JSONField (persistent cache in DB)
#      → All insight data stored in ONE JSON column (cleaner, no schema change for new keys)
#      → Dashboard always shows last known data even if Mailchimp is down
#   4. Also saves to MarketingEvent DB (audit trail)
#   5. Also fires send_to_zapier_mailchimp_insights() for any Zapier automations
#   6. Returns full insights JSON to FE
# =====================================================
class CampaignMailchimpInsightsAPIView(APIView):
    """
    GET /api/campaigns/<campaign_id>/mailchimp-insights/

    Fetches Mailchimp campaign insights (opens, clicks, bounces, etc.).
    - Reads directly from Mailchimp API for immediate response
    - Saves result to CampaignEmailConfig.insights JSONField (persistent cache)
      → Single JSON column: emails_sent, opens, open_rate, clicks, click_rate,
        bounces, unsubscribes, last_open, last_click, synced_at
    - Saves result to MarketingEvent DB for audit/history
    - Also triggers Zapier webhook (ZAPIER_WEBHOOK_MAILCHIMP_INSIGHTS_URL)
      so Zapier can react to the insights fetch event

    Response:
        {
            "campaign_id":           "<uuid>",
            "mailchimp_campaign_id": "<mailchimp-id>",
            "campaign_name":         "Pallavi",
            "insights": {
                "emails_sent":   6,
                "opens":         3,
                "open_rate":     "50.0%",
                "clicks":        1,
                "click_rate":    "16.7%",
                "bounces":       0,
                "unsubscribes":  0,
                "last_open":     "2026-03-10T07:18:00",
                "last_click":    "2026-03-10T07:20:00"
            }
        }
    """

    def get(self, request, campaign_id):
        try:
            campaign = get_object_or_404(Campaign, id=campaign_id)

            # ── Guard: campaign must have a Mailchimp campaign ID ──────────
            if not campaign.mailchimp_campaign_id:
                return Response(
                    {
                        "error": "No Mailchimp campaign ID linked to this campaign. "
                                 "The campaign may not have been sent via Mailchimp yet."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ── Step 1: Fetch directly from Mailchimp API ──────────────────
            report = get_mailchimp_campaign_report(campaign.mailchimp_campaign_id)

            if not report:
                return Response(
                    {"error": "Could not fetch Mailchimp report. The campaign may not have been sent yet."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ── Step 2: Save insights to CampaignEmailConfig (persistent DB cache) ──
            # Stores ALL insight data in the single insights JSONField.
            # This means the dashboard ALWAYS has last known data
            # even if Mailchimp API is temporarily unavailable.
            # No individual columns — just one clean JSON dict.
            email_config = campaign.email_configs.filter(is_active=True).first()
            if email_config:
                # ── Save all insight data to the single insights JSONField ──
                email_config.insights = {
                    "emails_sent":  report.get("emails_sent", 0),
                    "opens":        report.get("opens", 0),
                    "open_rate":    report.get("open_rate", 0),
                    "clicks":       report.get("clicks", 0),
                    "click_rate":   report.get("click_rate", 0),
                    "bounces":      report.get("bounces", 0),
                    "unsubscribes": report.get("unsubscribes", 0),
                    "last_open":    report.get("last_open"),    # stored as ISO string — no DateTimeField needed
                    "last_click":   report.get("last_click"),   # stored as ISO string — no DateTimeField needed
                    "synced_at":    timezone.now().isoformat(),
                }

                # ── Single save — only the insights JSON column ──
                email_config.save(update_fields=["insights"])

                logger.info(
                    f"[MailchimpInsights] Saved to CampaignEmailConfig.insights (JSONField) "
                    f"id={email_config.id} for campaign: {campaign_id}"
                )
            else:
                logger.warning(
                    f"[MailchimpInsights] No active CampaignEmailConfig found for campaign: {campaign_id}. "
                    f"Insights not cached to email config table."
                )

            # ── Step 3: Also save to MarketingEvent DB (audit trail) ───────
            MarketingEvent.objects.create(
                source=MarketingEvent.Source.MAILCHIMP,
                event_type="campaign_insights_fetched",
                payload={
                    "campaign_id":            str(campaign_id),
                    "mailchimp_campaign_id":  campaign.mailchimp_campaign_id,
                    "campaign_name":          campaign.campaign_name,
                    "emails_sent":            report.get("emails_sent", 0),
                    "opens":                  report.get("opens", 0),
                    "open_rate":              report.get("open_rate", 0),
                    "clicks":                 report.get("clicks", 0),
                    "click_rate":             report.get("click_rate", 0),
                    "bounces":                report.get("bounces", 0),
                    "unsubscribes":           report.get("unsubscribes", 0),
                    "last_open":              report.get("last_open"),
                    "last_click":             report.get("last_click"),
                }
            )

            logger.info(
                f"[MailchimpInsights] Fetched & saved for campaign: {campaign_id} "
                f"| mailchimp_id: {campaign.mailchimp_campaign_id}"
            )

            # ── Step 4: Also trigger Zapier for any downstream automations ─
            # This fires-and-forgets — insights are already in the response
            # Zapier can use this to: send Slack alerts, update sheets, etc.
            send_to_zapier_mailchimp_insights({
                "event":                  "mailchimp_insights_requested",
                "campaign_id":            str(campaign_id),
                "mailchimp_campaign_id":  campaign.mailchimp_campaign_id,
                "campaign_name":          campaign.campaign_name,
                "emails_sent":            report.get("emails_sent", 0),
                "opens":                  report.get("opens", 0),
                "open_rate":              report.get("open_rate", 0),
                "clicks":                 report.get("clicks", 0),
                "click_rate":             report.get("click_rate", 0),
                "bounces":                report.get("bounces", 0),
                "unsubscribes":           report.get("unsubscribes", 0),
                "last_open":              report.get("last_open"),
                "last_click":             report.get("last_click"),
            })

            # ── Step 5: Return insights to FE ──────────────────────────────
            return Response(
                {
                    "campaign_id":           str(campaign_id),
                    "mailchimp_campaign_id": campaign.mailchimp_campaign_id,
                    "campaign_name":         campaign.campaign_name,
                    "insights": {
                        "emails_sent":   report.get("emails_sent", 0),
                        "opens":         report.get("opens", 0),
                        "open_rate":     f"{report.get('open_rate', 0)}%",
                        "clicks":        report.get("clicks", 0),
                        "click_rate":    f"{report.get('click_rate', 0)}%",
                        "bounces":       report.get("bounces", 0),
                        "unsubscribes":  report.get("unsubscribes", 0),
                        "last_open":     report.get("last_open"),
                        "last_click":    report.get("last_click"),
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Mailchimp Insights Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# NEW: MAILCHIMP INSIGHTS CALLBACK API (POST from Zapier)
# POST /api/mailchimp/insights-callback/
#
# Flow:
#   Zapier receives the insights event from ZAPIER_WEBHOOK_MAILCHIMP_INSIGHTS_URL
#   Zapier processes it (e.g. fetches extra data, sends Slack notification)
#   Zapier POSTs back here with processed insights data
#   We store the callback in MarketingEvent DB
# =====================================================
class MailchimpInsightsCallbackAPIView(APIView):
    """
    POST /api/mailchimp/insights-callback/

    Receives Mailchimp insights data back from Zapier.
    Stores the result in MarketingEvent DB with event_type='campaign_insights_callback'.

    Expected payload from Zapier:
        {
            "campaign_id":           "<uuid>",
            "mailchimp_campaign_id": "<mailchimp-id>",
            "campaign_name":         "...",
            "emails_sent":           6,
            "opens":                 3,
            "open_rate":             50.0,
            "clicks":                1,
            "click_rate":            16.7,
            "bounces":               0,
            "unsubscribes":          0,
            "last_open":             "2026-03-10T07:18:00",
            "last_click":            "2026-03-10T07:20:00"
        }
    """

    def post(self, request):
        try:
            data = request.data

            print("📩 Mailchimp Insights Callback received:")
            print(data)

            # ── Save callback payload to MarketingEvent DB ─────────────────
            MarketingEvent.objects.create(
                source=MarketingEvent.Source.MAILCHIMP,
                event_type="campaign_insights_callback",
                payload={
                    "campaign_id":           data.get("campaign_id"),
                    "mailchimp_campaign_id": data.get("mailchimp_campaign_id"),
                    "campaign_name":         data.get("campaign_name"),
                    "emails_sent":           data.get("emails_sent", 0),
                    "opens":                 data.get("opens", 0),
                    "open_rate":             data.get("open_rate", 0),
                    "clicks":                data.get("clicks", 0),
                    "click_rate":            data.get("click_rate", 0),
                    "bounces":               data.get("bounces", 0),
                    "unsubscribes":          data.get("unsubscribes", 0),
                    "last_open":             data.get("last_open"),
                    "last_click":            data.get("last_click"),
                }
            )

            logger.info(
                f"[MailchimpInsights] Callback stored for campaign: "
                f"{data.get('campaign_id')} | mailchimp_id: {data.get('mailchimp_campaign_id')}"
            )

            return Response(
                {
                    "status":      "received",
                    "campaign_id": data.get("campaign_id"),
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error(
                "Mailchimp Insights Callback Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# Ticket Create API View (POST)
# -------------------------------------------------------------------
class TicketCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new support ticket",
        request_body=TicketWriteSerializer,
        responses={
            201: TicketDetailSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request):
        try:
            serializer = TicketWriteSerializer(
                data=request.data,
                context={"request": request},
            )

            serializer.is_valid(raise_exception=True)

            ticket = serializer.save()

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket creation validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Create API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Update API View (PUT)
# -------------------------------------------------------------------
class TicketUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update an existing ticket (Full Update)",
        request_body=TicketWriteSerializer,
        responses={
            200: TicketDetailSerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def put(self, request, ticket_id):
        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TicketWriteSerializer(
                ticket,
                data=request.data,
                context={"request": request},
            )

            serializer.is_valid(raise_exception=True)

            updated_ticket = serializer.save()

            return Response(
                TicketDetailSerializer(updated_ticket).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket update validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Update API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket List API View (GET)
# -------------------------------------------------------------------
class TicketListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve paginated list of tickets with optional filters",
        manual_parameters=[
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("priority", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("lab_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("department_id", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("from_date", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("to_date", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: TicketListSerializer(many=True),
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request):
        try:
            queryset = Ticket.objects.filter(is_deleted=False)

            if request.query_params.get("status"):
                queryset = queryset.filter(status=request.query_params.get("status"))

            if request.query_params.get("priority"):
                queryset = queryset.filter(priority=request.query_params.get("priority"))

            if request.query_params.get("lab_id"):
                queryset = queryset.filter(lab_id=request.query_params.get("lab_id"))

            if request.query_params.get("department_id"):
                queryset = queryset.filter(department_id=request.query_params.get("department_id"))

            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
            start = (page - 1) * page_size
            end = start + page_size

            total_count = queryset.count()
            paginated_queryset = queryset[start:end]

            serializer = TicketListSerializer(paginated_queryset, many=True)

            return Response(
                {
                    "count": total_count,
                    "current_page": page,
                    "results": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Ticket List API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Detail API View (GET)
# -------------------------------------------------------------------
class TicketDetailAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve detailed information of a specific ticket",
        responses={
            200: TicketDetailSerializer,
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request, ticket_id):

        if getattr(self, "swagger_fake_view", False):
            return Response(status=200)

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TicketDetailSerializer(ticket)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Ticket Detail API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Assign for Employee API View (POST)
# -------------------------------------------------------------------
class TicketAssignAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Assign a ticket to an employee",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["assigned_to_id"],
            properties={
                "assigned_to_id": openapi.Schema(type=openapi.TYPE_STRING)
            },
        ),
        responses={
            200: TicketDetailSerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            assigned_to_id = request.data.get("assigned_to_id")
            assigned_to_name_raw = request.data.get("assigned_to_name")

            if not assigned_to_id:
                raise ValidationError("assigned_to_id is required")

            assigned_employee = Employee.objects.filter(id=assigned_to_id).first()
            assigned_to_name = (
                assigned_employee.emp_name
                if assigned_employee
                else str(assigned_to_name_raw).strip()
                if assigned_to_name_raw is not None
                else f"User {assigned_to_id}"
            )

            ticket.assigned_to_id = assigned_to_id
            ticket.assigned_to_name = assigned_to_name
            ticket.save()

            TicketTimeline.objects.create(
                ticket=ticket,
                action="Ticket Assigned",
                done_by_id=assigned_to_id,
                done_by_name=assigned_to_name,
            )

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket Assign validation failed: {validation_error}")
            return Response(
                {"error": str(validation_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Assign API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Status Update API View (POST)
# -------------------------------------------------------------------
class TicketStatusUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update the status of a ticket",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["status"],
            properties={
                "status": openapi.Schema(type=openapi.TYPE_STRING),
                "priority": openapi.Schema(type=openapi.TYPE_STRING),
                "assigned_to": openapi.Schema(type=openapi.TYPE_INTEGER),
                "assigned_to_name": openapi.Schema(type=openapi.TYPE_STRING),
                "type": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: TicketDetailSerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # -------- OLD VALUES --------
            old_status = ticket.status
            old_priority = ticket.priority
            old_assigned = ticket.assigned_to_id
            old_assigned_name = ticket.assigned_to_name or "Unassigned"
            old_type = ticket.type

            # -------- REQUEST VALUES --------
            new_status = request.data.get("status")
            new_priority = request.data.get("priority")
            new_assigned = request.data.get("assigned_to")
            new_assigned_name_raw = request.data.get("assigned_to_name")
            new_type = request.data.get("type")
            has_assigned_field = "assigned_to" in request.data

            def resolve_assignee_name(assignee_id, fallback_name):
                if not assignee_id:
                    return None

                employee = Employee.objects.filter(id=assignee_id).first()
                if employee:
                    return employee.emp_name

                fallback = (
                    str(fallback_name).strip()
                    if fallback_name is not None
                    else ""
                )
                return fallback or f"User {assignee_id}"

            if not new_status:
                raise ValidationError("status field is required")

            # -------- UPDATE STATUS --------
            ticket.status = new_status

            if new_status == "resolved":
                ticket.resolved_at = timezone.now()

            if new_status == "closed":
                ticket.closed_at = timezone.now()

            # -------- UPDATE PRIORITY --------
            if new_priority:
                ticket.priority = new_priority

            # -------- UPDATE ASSIGN --------
            if has_assigned_field:
                normalized_assigned = (
                    None
                    if new_assigned in (None, "")
                    else int(new_assigned)
                )
                ticket.assigned_to_id = normalized_assigned
                ticket.assigned_to_name = resolve_assignee_name(
                    normalized_assigned,
                    new_assigned_name_raw,
                )

            # -------- UPDATE TYPE --------
            if new_type:
                ticket.type = new_type

            ticket.save()

            # -------- TIMELINE --------

            if old_status != new_status:
                TicketTimeline.objects.create(
                    ticket=ticket,
                    action=f"Status changed from {old_status} to {new_status}",
                    done_by_id=ticket.assigned_to_id,
                    done_by_name=ticket.assigned_to_name,
                )

            if new_priority and old_priority != new_priority:
                TicketTimeline.objects.create(
                    ticket=ticket,
                    action=f"Priority changed from {old_priority} to {new_priority}",
                    done_by_id=ticket.assigned_to_id,
                    done_by_name=ticket.assigned_to_name,
                )

            if new_type and old_type != new_type:
                TicketTimeline.objects.create(
                    ticket=ticket,
                    action=f"Type changed from {old_type} to {new_type}",
                    done_by_id=ticket.assigned_to_id,
                    done_by_name=ticket.assigned_to_name,
                )

            # -------- ASSIGN TIMELINE (SAFE FIX) --------
            if has_assigned_field:
                normalized_assigned = ticket.assigned_to_id
                if old_assigned != normalized_assigned:
                    new_user_name = ticket.assigned_to_name or "Unassigned"

                    TicketTimeline.objects.create(
                        ticket=ticket,
                        action=f"Assigned changed from {old_assigned_name} to {new_user_name}",
                        done_by_id=normalized_assigned,
                        done_by_name=new_user_name,
                    )

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket Status validation failed: {validation_error}")
            return Response(
                {"error": str(validation_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Status API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# -------------------------------------------------------------------
# Ticket Document Upload API View (POST)
# -------------------------------------------------------------------
class TicketDocumentUploadAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Upload a document to a ticket",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["file"],
            properties={
                "file": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_BINARY
                )
            },
        ),
        responses={
            201: openapi.Schema(type=openapi.TYPE_OBJECT),
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):

        if getattr(self, "swagger_fake_view", False):
            return Response(status=200)

        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            uploaded_file = request.FILES.get("file")

            if not uploaded_file:
                raise ValidationError("File is required")

            Document.objects.create(
                ticket=ticket,
                file=uploaded_file
            )

            return Response(
                TicketDetailSerializer(ticket).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(
                f"Document Upload validation failed: {validation_error}"
            )
            return Response(
                {"error": str(validation_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Document Upload API Error:\n" +
                traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Delete API View (DELETE)
# -------------------------------------------------------------------
class TicketDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete a ticket",
        responses={
            200: "Ticket deleted successfully",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def delete(self, request, ticket_id):
        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            ticket.is_deleted = True
            ticket.deleted_at = timezone.now()
            ticket.save()

            return Response(
                {"message": "Ticket deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Ticket Delete API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# Ticket Dashboard Count API View (GET)
# -------------------------------------------------------------------
class TicketDashboardCountAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Get ticket count grouped by status",
        responses={
            200: "Ticket count response",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def get(self, request):
        try:
            queryset = Ticket.objects.filter(is_deleted=False)

            response_data = {
                "new": queryset.filter(status="new").count(),
                "pending": queryset.filter(status="pending").count(),
                "resolved": queryset.filter(status="resolved").count(),
                "closed": queryset.filter(status="closed").count(),
                "total": queryset.count(),
            }

            return Response(
                response_data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.error("Dashboard Count API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# LAB CREATE API
# -------------------------------------------------------------------
class LabCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create a new lab",
        request_body=LabWriteSerializer,
        responses={
            201: LabReadSerializer,
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Labs"],
    )
    def post(self, request):
        try:
            serializer = LabWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            lab = serializer.save()

            return Response(
                LabReadSerializer(lab).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as ve:
            return Response(
                {"error": ve.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )


# -------------------------------------------------------------------
# LAB LIST API
# -------------------------------------------------------------------
class LabListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List all active labs",
        responses={200: LabReadSerializer(many=True)},
        tags=["Labs"],
    )
    def get(self, request):

        labs = Lab.objects.filter(
            is_deleted=False,
            is_active=True
        )

        return Response(
            LabReadSerializer(labs, many=True).data,
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# LAB UPDATE API
# -------------------------------------------------------------------
class LabUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Update lab",
        request_body=LabWriteSerializer,
        responses={
            200: LabReadSerializer,
            404: "Lab not found",
        },
        tags=["Labs"],
    )
    def put(self, request, lab_id):

        lab = get_object_or_404(
            Lab,
            id=lab_id,
            is_deleted=False
        )

        serializer = LabWriteSerializer(
            lab,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        updated_lab = serializer.save()

        return Response(
            LabReadSerializer(updated_lab).data,
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# LAB SOFT DELETE API
# -------------------------------------------------------------------
class LabSoftDeleteAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Soft delete lab",
        tags=["Labs"],
    )
    def delete(self, request, lab_id):

        lab = get_object_or_404(
            Lab,
            id=lab_id,
            is_deleted=False
        )

        lab.is_deleted = True
        lab.is_active = False
        lab.save()

        return Response(
            {"message": "Lab deleted successfully"},
            status=status.HTTP_200_OK,
        )

# -------------------------------------------------------------------
# TEMPLATE LIST API (GET)
# -------------------------------------------------------------------
class TemplateListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="List Templates by type (mail, sms, whatsapp)",
    )
    def get(self, request, template_type):
        try:
            if template_type == "mail":
                templates = TemplateMail.objects.filter(is_deleted=False)
                serializer = TemplateMailReadSerializer(templates, many=True)

            elif template_type == "sms":
                templates = TemplateSMS.objects.filter(is_deleted=False)
                serializer = TemplateSMSReadSerializer(templates, many=True)

            elif template_type == "whatsapp":
                templates = TemplateWhatsApp.objects.filter(is_deleted=False)
                serializer = TemplateWhatsAppReadSerializer(templates, many=True)

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as validation_error:
            logger.warning(f"Template List validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template List Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# -------------------------------------------------------------------
# TEMPLATE DETAIL API (GET)
# -------------------------------------------------------------------
class TemplateDetailAPIView(APIView):

    def get(self, request, template_type, template_id):
        try:

            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateMailReadSerializer(template_instance)

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateSMSReadSerializer(template_instance)

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateWhatsAppReadSerializer(template_instance)

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as validation_error:
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE CREATE API (POST)
# -------------------------------------------------------------------
class TemplateCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Template (mail, sms, whatsapp)",
    )
    def post(self, request, template_type):
        try:
            if template_type == "mail":
                write_serializer = TemplateMailSerializer(data=request.data)
                read_serializer_class = TemplateMailReadSerializer

            elif template_type == "sms":
                write_serializer = TemplateSMSSerializer(data=request.data)
                read_serializer_class = TemplateSMSReadSerializer

            elif template_type == "whatsapp":
                write_serializer = TemplateWhatsAppSerializer(data=request.data)
                read_serializer_class = TemplateWhatsAppReadSerializer

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            write_serializer.is_valid(raise_exception=True)
            template_instance = write_serializer.save()

            return Response(
                read_serializer_class(template_instance).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Create validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Create Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE UPDATE API (PUT)
# -------------------------------------------------------------------
class TemplateUpdateAPIView(APIView):

    def put(self, request, template_type, template_id):
        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateMailSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateMailReadSerializer

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateSMSSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateSMSReadSerializer

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = TemplateWhatsAppSerializer(
                    template_instance,
                    data=request.data,
                    partial=True
                )

                read_serializer_class = TemplateWhatsAppReadSerializer

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            serializer.is_valid(raise_exception=True)
            updated_template = serializer.save()

            return Response(
                read_serializer_class(updated_template).data,
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Update validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Update Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE DOCUMENT UPLOAD API (POST)
# -------------------------------------------------------------------
class TemplateDocumentUploadAPIView(APIView):

    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Upload a document to a template (mail, sms, whatsapp)",
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="The file to upload"
            )
        ],
        responses={
            201: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_STRING),
                    "file": openapi.Schema(type=openapi.TYPE_STRING),
                    "uploaded_at": openapi.Schema(type=openapi.TYPE_STRING),
                    "template_id": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
            400: "Validation Error",
            404: "Template Not Found",
            500: "Internal Server Error",
        },
        tags=["Templates"],
    )
    def post(self, request, template_type, template_id):

        if getattr(self, "swagger_fake_view", False):
            return Response(status=200)

        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "Mail template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                DocumentModel = TemplateMailDocument

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "SMS template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                DocumentModel = TemplateSMSDocument

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

                if not template_instance:
                    return Response(
                        {"error": "WhatsApp template not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                DocumentModel = TemplateWhatsAppDocument

            else:
                return Response(
                    {"error": "Invalid template type. Allowed values: mail, sms, whatsapp."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            uploaded_file = request.FILES.get("file")

            if not uploaded_file:
                return Response(
                    {"error": "No file was submitted. Send the file under the key 'file'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            document = DocumentModel.objects.create(
                template=template_instance,
                file=uploaded_file,
            )

            logger.info(
                f"Template document uploaded: type={template_type}, "
                f"template_id={template_id}, doc_id={document.id}, "
                f"file={uploaded_file.name}"
            )

            return Response(
                {
                    "id": str(document.id),
                    "file": document.file.url if document.file else None,
                    "uploaded_at": document.uploaded_at.isoformat() if hasattr(document, 'uploaded_at') else None,
                    "template_id": str(template_id),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception:
            logger.error(
                "Template Document Upload Error:\n" + traceback.format_exc()
            )
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# -------------------------------------------------------------------
# TEMPLATE SOFT DELETE API (DELETE)
# -------------------------------------------------------------------
class TemplateDeleteAPIView(APIView):

    def delete(self, request, template_type, template_id):
        try:
            if template_type == "mail":
                template_instance = TemplateMail.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            elif template_type == "sms":
                template_instance = TemplateSMS.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            elif template_type == "whatsapp":
                template_instance = TemplateWhatsApp.objects.filter(
                    id=template_id,
                    is_deleted=False
                ).first()

            else:
                raise ValidationError(
                    "Invalid template type. Allowed values: mail, sms, whatsapp."
                )

            if not template_instance:
                return Response(
                    {"error": "Template not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            template_instance.is_deleted = True
            template_instance.save()

            return Response(
                {"message": "Template deleted successfully."},
                status=status.HTTP_200_OK,
            )

        except ValidationError as validation_error:
            logger.warning(f"Template Delete validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Template Delete Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# =====================================================
# SOCIAL AUTH - LINKEDIN
# =====================================================
class LinkedInLoginAPIView(APIView):
    def get(self, request):
        auth_url = (
            "https://www.linkedin.com/oauth/v2/authorization"
            "?response_type=code"
            f"&client_id={settings.LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
            "&scope=openid%20profile%20email"
            "&prompt=login"
        )
        return redirect(auth_url)


class LinkedInCallbackAPIView(APIView):
    def get(self, request):
        code = request.GET.get("code")
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }
        response = requests.post(token_url, data=data)
        token_data = response.json()
        access_token = token_data.get("access_token")
        if access_token:
            request.session["linkedin_token"] = access_token
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}?linkedin=connected")


class LinkedInStatusAPIView(APIView):
    def get(self, request):
        return Response({"connected": bool(request.session.get("linkedin_token"))})


# =====================================================
# IMAGE UPLOAD API
# =====================================================
class ImageUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            file = request.FILES.get("file")
            if not file:
                return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
            from django.core.files.storage import default_storage
            path = default_storage.save(f"campaign_images/{file.name}", file)
            url = request.build_absolute_uri(settings.MEDIA_URL + path)
            print(f"Image uploaded: {url} | path: {path}")
            return Response({"url": url, "path": path}, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Image Upload Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =====================================================
# SOCIAL AUTH - FACEBOOK
# =====================================================
class FacebookLoginAPIView(APIView):
    def get(self, request):
        state = secrets.token_urlsafe(16)
        request.session["facebook_state"] = state
        auth_url = (
            "https://www.facebook.com/v19.0/dialog/oauth"
            "?response_type=code"
            f"&client_id={settings.FACEBOOK_CLIENT_ID}"
            f"&redirect_uri={settings.FACEBOOK_REDIRECT_URI}"
            "&scope=public_profile,email,pages_show_list,pages_read_engagement,pages_manage_posts,read_insights"
            f"&state={state}"
            "&auth_type=rerequest"
        )
        print("FB APP ID:", settings.FACEBOOK_CLIENT_ID, auth_url)
        return redirect(auth_url)


class FacebookCallbackAPIView(APIView):
    def get(self, request):
        try:
            code = request.GET.get("code")
            params = {
                "client_id": settings.FACEBOOK_CLIENT_ID,
                "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
                "code": code,
            }
            response = requests.get("https://graph.facebook.com/v19.0/oauth/access_token", params=params)
            data = response.json()
            if "access_token" not in data:
                return Response(data)
            user_token = data["access_token"]
            pages_response = requests.get(
                "https://graph.facebook.com/v19.0/me/accounts",
                params={"access_token": user_token},
            )
            pages_data = pages_response.json()
            if not pages_data.get("data"):
                return Response({"error": "No pages found"})
            page = pages_data["data"][0]
            clinic = Clinic.objects.first()
            SocialAccount.objects.update_or_create(
                clinic=clinic,
                platform="facebook",
                defaults={
                    "access_token": page["access_token"],
                    "user_token": user_token,
                    "page_id": page["id"],
                    "page_name": page["name"],
                    "is_active": True,
                },
            )
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?facebook=connected&page={page['name']}"
            )
        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)})


class FacebookStatusAPIView(APIView):
    def get(self, request):
        clinic = Clinic.objects.first()
        connected = SocialAccount.objects.filter(clinic=clinic, platform="facebook", is_active=True).exists()
        return Response({"connected": connected})


# =====================================================
# MAIL INSIGHTS APIs
# =====================================================
class MailInsightsReceiveAPIView(APIView):
    """
    POST /api/mail-insights/

    Receives mail insight counts pushed from Zapier.

    CRITICAL FIX — accumulate, never overwrite:
      Each Zapier Zap sends only ITS own field, e.g.:
        Appointment Booked Zap  →  { "appointments_booked": 1 }
        Lead Created Zap        →  { "leads_created": 1 }

      We READ the existing cache first, then ADD the incoming delta.
      A "leads_created=1" POST can NEVER reset appointments_booked to 0.

    Cache TTL: 30 days (2592000 seconds) — survives server restarts longer.
    """

    def post(self, request):
        try:
            data = request.data

            # ── Step 1: Load whatever is currently cached ──────────────────
            existing = cache.get("mail_insights") or {
                "leads_created":       0,
                "appointments_booked": 0,
                "leads_updated":       0,
                "last_synced":         None,
            }

            # ── Step 2: Only add what Zapier actually sent this time ───────
            # If key is absent from POST body → default 0 → no change to total
            incoming_leads        = int(data.get("leads_created", 0))
            incoming_appointments = int(data.get("appointments_booked", 0))
            incoming_updated      = int(data.get("leads_updated", 0))

            payload = {
                "leads_created":       existing["leads_created"]       + incoming_leads,
                "appointments_booked": existing["appointments_booked"] + incoming_appointments,
                "leads_updated":       existing["leads_updated"]       + incoming_updated,
                "last_synced":         timezone.now().isoformat(),
            }

            # ── Step 3: Save accumulated totals for 30 days ───────────────
            cache.set("mail_insights", payload, timeout=2592000)

            logger.info(
                f"[MailInsights] POST received | "
                f"incoming appts={incoming_appointments} leads={incoming_leads} | "
                f"new totals={payload}"
            )
            return Response({"status": "received", "data": payload}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Mail Insights Receive Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MailInsightsGetAPIView(APIView):
    """
    GET /api/mail-insights/get/

    Returns accumulated mail insight counts for the React dashboard KPI cards.

    DB FALLBACK (so KPI cards NEVER show 0 even if cache is cleared):
      1. Try cache first  → fast, always current after Zapier fires
      2. Cache miss?      → count Lead rows directly from DB
                            leads_created       = total non-deleted leads
                            appointments_booked = leads where status contains "appointment"
         Also repopulates cache so the next request is fast again.
    """

    def get(self, request):
        try:
            payload = cache.get("mail_insights")

            if not payload:
                # ── Cache miss: rebuild counts from DB ─────────────────────
                appointments_count = Lead.objects.filter(
                    is_deleted=False,
                    lead_status__icontains="appointment"
                ).count()

                leads_count = Lead.objects.filter(is_deleted=False).count()

                payload = {
                    "leads_created":       leads_count,
                    "appointments_booked": appointments_count,
                    "leads_updated":       0,
                    "last_synced":         None,
                    "_source":             "db_fallback",  # visible in API response for debugging
                }

                # Repopulate cache so next call is fast
                cache.set("mail_insights", payload, timeout=2592000)
                logger.info(f"[MailInsights] Cache miss — rebuilt from DB: {payload}")

            return Response(payload, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Mail Insights Get Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MailInsightsResetAPIView(APIView):
    """
    POST /api/mail-insights/reset/

    Resets all mail insight counts back to 0.
    Use this if counts get corrupted or for testing a fresh start.

    Example:
      POST http://localhost:8000/api/mail-insights/reset/
      → { "status": "reset", "data": { "leads_created": 0, ... } }
    """

    def post(self, request):
        try:
            payload = {
                "leads_created":       0,
                "appointments_booked": 0,
                "leads_updated":       0,
                "last_synced":         timezone.now().isoformat(),
            }
            cache.set("mail_insights", payload, timeout=604800)
            logger.info("Mail Insights cache reset to 0.")
            return Response({"status": "reset", "data": payload}, status=status.HTTP_200_OK)
        except Exception:
            logger.error("Mail Insights Reset Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =====================================================
# DEBUG API — Temporary: check what Twilio statuses are in DB
# GET /api/debug/twilio-status/
# Remove this endpoint once you've confirmed the status values.
# =====================================================
class TwilioDebugAPIView(APIView):
    """
    GET /api/debug/twilio-status/
    Shows all status values stored in TwilioCall and TwilioMessage tables.
    Use this to confirm what statuses Twilio is saving so we can map them correctly.
    Remove after debugging.
    """
    def get(self, request):
        from django.db.models import Count

        call_statuses = (
            TwilioCall.objects
            .values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        sms_statuses = (
            TwilioMessage.objects
            .values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response({
            "total_calls":    TwilioCall.objects.count(),
            "total_messages": TwilioMessage.objects.count(),
            "call_statuses":  list(call_statuses),
            "sms_statuses":   list(sms_statuses),
        }, status=status.HTTP_200_OK)


# =====================================================
# MAIL INSIGHTS DEBUG API — Temporary diagnostic tool
# GET /api/debug/mail-insights-log/
# Open in browser to see if Zapier is hitting Django.
# Remove after confirming flow works end-to-end.
# =====================================================
class MailInsightsDebugAPIView(APIView):
    """
    GET /api/debug/mail-insights-log/
    Shows current cache state + DB lead counts.
    Use this to verify Zapier is actually posting to your endpoint.
    """

    def get(self, request):
        try:
            cached = cache.get("mail_insights")

            appointments_in_db = Lead.objects.filter(
                is_deleted=False,
                lead_status__icontains="appointment"
            ).count()

            all_leads_in_db = Lead.objects.filter(is_deleted=False).count()

            recent_statuses = list(
                Lead.objects.filter(is_deleted=False)
                .order_by("-created_at")
                .values("full_name", "lead_status", "created_at")[:5]
            )

            return Response({
                "cache_state": cached or "EMPTY — Zapier has not posted yet (or cache was cleared)",
                "db_counts": {
                    "total_leads":       all_leads_in_db,
                    "appointment_leads": appointments_in_db,
                },
                "recent_lead_statuses": recent_statuses,
                "instructions": {
                    "appointment_zap_body": {"appointments_booked": 1},
                    "lead_created_zap_body": {"leads_created": 1},
                    "zapier_must_post_to": "http://YOUR_PUBLIC_IP:8000/api/mail-insights/",
                    "note": "Zapier cannot reach localhost — use ngrok or public IP",
                },
            }, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Mail Insights Debug Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =====================================================
# INTERACTION COUNTS API
# GET /api/interactions/counts/
# Feeds the CommunicationChart with REAL data from:
#   Email    → Zapier cache  (mail_insights)
#   SMS      → TwilioMessage DB
#   Call     → TwilioCall    DB
#   WhatsApp → 0  (future scope)
#   Chatbot  → 0  (future scope)
#
# Engagement mapping:
#   Email:  appointments_booked → high | leads_created → low | 0 → no
#   SMS:    delivered/sent → high | failed/undelivered → low | queued/accepted → no
#   Call:   completed/in-progress/ringing → high | busy/no-answer → low | failed/canceled → no
#           Fallback: if no status matches but records exist → all go to high
# =====================================================
class InteractionCountsAPIView(APIView):
    """
    GET /api/interactions/counts/

    Returns per-platform interaction counts for the Communication chart.
    Order: Email → SMS → Call → WhatsApp → Chatbot
    """

    def get(self, request):
        try:
            # ── EMAIL — from LeadEmail DB ────────────────────────────────
            email_counts = LeadEmail.objects.aggregate(
                high=Count(
                    "id",
                    filter=Q(
                        status=LeadEmail.StatusChoices.SENT,
                        sent_at__isnull=False
                    )
                ),
                low=Count(
                    "id",
                    filter=Q(status=LeadEmail.StatusChoices.FAILED)
                ),
                no=Count(
                    "id",
                    filter=Q(
                        status__in=[
                            LeadEmail.StatusChoices.DRAFT,
                            LeadEmail.StatusChoices.SCHEDULED
                        ]
                    )
                )
            )

            email_high = email_counts["high"] or 0
            email_low  = email_counts["low"] or 0
            email_no   = email_counts["no"] or 0


            # ── SMS — from TwilioMessage DB ──────────────────────────────
            sms_counts = TwilioMessage.objects.aggregate(
                high=Count(
                    "id",
                    filter=Q(status__in=["delivered", "sent", "queued_via_zapier"])
                ),
                low=Count(
                    "id",
                    filter=Q(status__in=["failed", "undelivered"])
                ),
                no=Count(
                    "id",
                    filter=Q(status__in=["queued", "accepted", "sending", "receiving", "received"])
                )
            )

            sms_high = sms_counts["high"] or 0
            sms_low  = sms_counts["low"] or 0
            sms_no   = sms_counts["no"] or 0


            # ── CALLS — from TwilioCall DB ───────────────────────────────
            call_counts = TwilioCall.objects.aggregate(
                high=Count(
                    "id",
                    filter=Q(status__in=["completed", "in-progress", "ringing", "in_progress"])
                ),
                low=Count(
                    "id",
                    filter=Q(status__in=["busy", "no-answer", "no_answer"])
                ),
                no=Count(
                    "id",
                    filter=Q(status__in=["failed", "canceled"])
                )
            )

            call_high = call_counts["high"] or 0
            call_low  = call_counts["low"] or 0
            call_no   = call_counts["no"] or 0

            # Fallback: if no categorized calls but records exist
            total_calls = TwilioCall.objects.count()
            if call_high == 0 and call_low == 0 and call_no == 0 and total_calls > 0:
                call_high = total_calls


            # ── FINAL RESPONSE ──────────────────────────────────────────
            data = [
                {"platform": "Email",    "high": email_high, "low": email_low, "no": email_no},
                {"platform": "SMS",      "high": sms_high,   "low": sms_low,   "no": sms_no},
                {"platform": "Call",     "high": call_high,  "low": call_low,  "no": call_no},
                {"platform": "WhatsApp", "high": 0,          "low": 0,         "no": 0},
                {"platform": "Chatbot",  "high": 0,          "low": 0,         "no": 0},
            ]

            return Response(data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Interaction Counts Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

            # =====================================================
# =====================================================
# GOHIGHLEVEL WEBHOOK — Receives leads from Zapier LeadConnector
# POST /api/webhooks/gohighlevel/lead/
# =====================================================
class GoHighLevelLeadWebhookAPIView(APIView):
    def post(self, request):
        try:
            data = request.data
            print("GHL Webhook received:", data)

            # ── Extract name fields ──────────────────────────────────────
            first_name = data.get('first_name') or data.get('contact_first_name') or ""
            last_name  = data.get('last_name')  or data.get('contact_last_name')  or ""
            full_name  = f"{first_name} {last_name}".strip()

            if not full_name:
                full_name = (
                    data.get("contact_name") or
                    data.get("name") or
                    data.get("full_name") or
                    data.get("contact_full_name") or
                    "GHL Lead"
                )

            # ── Extract contact fields ───────────────────────────────────
            email = (
                data.get("email") or
                data.get("contact_email") or ""
            )
            phone = (
                data.get("phone") or
                data.get("phone_number") or
                data.get("contact_phone") or ""
            )

            # ── Extract location ─────────────────────────────────────────
            location = (
                data.get("city") or
                data.get("state") or
                data.get("country") or
                data.get("address1") or ""
            )

            # ── Truncate fields to fit DB column limits ──────────────────
            full_name = (full_name or "GHL Lead")[:255]
            email     = email[:254]
            phone     = phone[:20]
            location  = location[:255]

            # ── Get clinic ───────────────────────────────────────────────
            clinic = Clinic.objects.first()
            if not clinic:
                return Response(
                    {"error": "No clinic found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ── Get first department (required field in Lead model) ───────
            from restapi.models import Department
            department = Department.objects.filter(clinic=clinic).first()
            if not department:
                return Response(
                    {"error": "No department found for clinic"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ── Create lead ──────────────────────────────────────────────
            lead = Lead.objects.create(
                clinic=clinic,
                department=department,
                full_name=full_name,
                email=email,
                contact_no=phone,
                lead_status="new",
                source="facebook",
                location=location,
                is_active=True,
            )

            # ── Notify Zapier ────────────────────────────────────────────
            send_to_zapier({
                "event":       "lead_created",
                "lead_id":     str(lead.id),
                "clinic_id":   lead.clinic.id,
                "full_name":   lead.full_name,
                "contact_no":  lead.contact_no,
                "email":       lead.email,
                "lead_status": lead.lead_status,
                "source":      "facebook",
                "location":    location,
            })

            logger.info(f"[GHL Webhook] Lead created: {lead.id} | {full_name}")

            return Response(
                {
                    "status":   "lead_created",
                    "lead_id":  str(lead.id),
                    "name":     full_name,
                    "source":   "facebook",
                    "location": location,
                },
                status=status.HTTP_201_CREATED
            )

        except Exception:
            logger.error("GHL Webhook Error:\n" + traceback.format_exc())
            print("GHL Webhook Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =====================================================
# FACEBOOK ADS CAMPAIGN APIs (fb_business SDK)
# =====================================================
class FBCampaignListAPIView(APIView):
    """
    GET /api/fb/campaigns/
    Returns list of Facebook Ad campaigns
    """
    def get(self, request):
        try:
            token = settings.FB_ACCESS_TOKEN
            ad_account_id = settings.FB_AD_ACCOUNT_ID

            r = requests.get(
                f"https://graph.facebook.com/v19.0/act_{ad_account_id}/campaigns",
                params={
                    "fields": "id,name,status,objective,daily_budget,created_time",
                    "access_token": token,
                }
            )
            data = r.json()

            if "error" in data:
                return Response({
                    "error": data["error"]["message"],
                    "note": "Need ads_read permission — complete Meta Developer registration"
                }, status=400)

            return Response({
                "campaigns": data.get("data", []),
                "total": len(data.get("data", []))
            }, status=200)

        except Exception:
            logger.error("FB Campaign List Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


class FBCampaignInsightsAPIView(APIView):
    """
    GET /api/fb/campaigns/<campaign_id>/insights/
    Returns impressions, clicks, reach, spend, leads
    """
    def get(self, request, campaign_id):
        try:
            token = settings.FB_ACCESS_TOKEN
            date_preset = request.query_params.get('date_preset', 'maximum')

            r = requests.get(
                f"https://graph.facebook.com/v19.0/{campaign_id}/insights",
                params={
                    "fields": "campaign_name,impressions,clicks,reach,spend,cpc,cpm,actions",
                    "date_preset": date_preset,
                    "access_token": token,
                }
            )
            data = r.json()

            if "error" in data:
                return Response({
                    "error": data["error"]["message"],
                    "note": "Need ads_read permission"
                }, status=400)

            insights = data.get("data", [])
            if not insights:
                return Response({
                    "insights": {
                        "post_impressions": 0,
                        "post_clicks": 0,
                        "post_engaged_users": 0,
                        "spend": "0",
                        "reach": "0",
                        "cpc": "0",
                        "cpm": "0",
                    },
                    "message": "No data yet - campaign has no spend"
                }, status=200)

            i = insights[0]
            return Response({
                "insights": {
                    "post_impressions": int(i.get("impressions", 0)),
                    "post_clicks": int(i.get("clicks", 0)),
                    "post_engaged_users": int(i.get("reach", 0)),
                    "spend": i.get("spend", "0"),
                    "reach": i.get("reach", "0"),
                    "cpc": i.get("cpc", "0"),
                    "cpm": i.get("cpm", "0"),
                }
            }, status=200)

        except Exception:
            logger.error("FB Insights Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)

class FBCampaignCreateAPIView(APIView):
    """
    POST /api/fb/campaigns/create/
    Creates a new Facebook Ad campaign
    Body: { "name": "...", "objective": "OUTCOME_LEADS", "daily_budget": 200, "status": "PAUSED" }
    """
    def post(self, request):
        try:
            token = settings.FB_ACCESS_TOKEN
            ad_account_id = settings.FB_AD_ACCOUNT_ID

            name = request.data.get("name", "New Campaign")
            objective = request.data.get("objective", "OUTCOME_LEADS")
            status = request.data.get("status", "PAUSED")
            daily_budget = int(request.data.get("daily_budget", 200)) * 100  # convert to paise

            r = requests.post(
                f"https://graph.facebook.com/v19.0/act_{ad_account_id}/campaigns",
                data={
                    "name": name,
                    "objective": objective,
                    "status": status,
                    "daily_budget": daily_budget,
                    "special_ad_categories": "[]",
                    "is_adset_budget_sharing_enabled": False,
                    "access_token": token,
                }
            )
            data = r.json()
            if "error" in data:
                return Response({
                    "error": data["error"]["message"]
                }, status=400)

            fb_campaign_id = data.get("id")

            # Save to Django DB
            try:
                from datetime import date
                campaign = Campaign.objects.create(
                    clinic=Clinic.objects.first(),
                    campaign_name=name,
                    campaign_description="Created via Zapier/API",
                    campaign_objective="leads",
                    target_audience="all",
                    start_date=date.today(),
                    end_date=date.today(),
                    campaign_mode=Campaign.PAID,
                    fb_campaign_id=fb_campaign_id,
                    is_active=True,
                )
                print("Campaign saved to DB:", campaign.id)
            except Exception:
                print("DB save failed:\n" + traceback.format_exc())

            return Response({
                "success": True,
                "campaign_id": fb_campaign_id,
                "name": name,
                "status": status,
                "message": "Campaign created successfully on Facebook and saved to DB!"
            }, status=201)

        except Exception:
            logger.error("FB Campaign Create Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)

        

# =====================================================
# =====================================================
# REPUTATION MANAGEMENT - CREATE REVIEW REQUEST
# POST /api/reputation/review-request/

class ReviewRequestCreateAPIView(APIView):

    def post(self, request):

        serializer = ReviewRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        review_request = serializer.save()
        delivery_report = getattr(review_request, "_delivery_report", None)

        response_status = "success"
        response_message = "Review request created"

        if delivery_report and delivery_report.get("failed_count"):
            if delivery_report.get("success_count"):
                response_status = "partial_success"
                response_message = "Review request created with some delivery failures"
            else:
                response_status = "error"
                response_message = "Review request created but no messages were delivered"

        return Response(
            {
                "status": response_status,
                "message": response_message,
                "data": serializer.data,
                "delivery_report": delivery_report,
            },
            status=status.HTTP_201_CREATED
        )

# REPUTATION MANAGEMENT - LIST REVIEW REQUESTS  
# GET /api/reputation/review-requests/
class ReviewRequestListAPIView(APIView):

    def get(self, request):

        review_requests = ReviewRequest.objects.all().prefetch_related("leads", "reviews").order_by("-created_at")

        serializer = ReviewRequestSerializer(review_requests, many=True)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            }
        )

# REPUTATION MANAGEMENT - REVIEW REQUEST DETAIL 
# GET /api/reputation/review-request/<request_id>/

class ReviewRequestDetailAPIView(APIView):

    def get(self, request, request_id):

        review_request = get_object_or_404(
            ReviewRequest.objects.prefetch_related("leads", "reviews"),
            id=request_id,
        )

        serializer = ReviewRequestSerializer(review_request)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

# REPUTATION MANAGEMENT - LIST REVIEWS FOR A REQUEST
# GET /api/reputation/review-request/<request_id>/reviews/
class ReviewListAPIView(APIView):
    def get(self, request, request_id):

        reviews = Review.objects.filter(review_request_id=request_id)

        serializer = ReviewSerializer(reviews, many=True)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            }
        )

# REPUTATION MANAGEMENT - SUBMIT REVIEW
# POST /api/reputation/submit-review/
class ReviewCreateAPIView(APIView):

    def post(self, request):

        serializer = ReviewSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            ReviewRequestLead.objects.filter(
                review_request_id=serializer.instance.review_request_id,
                lead_id=serializer.instance.lead_id,
            ).update(review_submitted=True)

            return Response(
                {
                    "status": "success",
                    "message": "Review submitted successfully",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            {
                "status": "error",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

# REPUTATION MANAGEMENT - DASHBOARD INSIGHTS
# GET /api/reputation/dashboard/
class ReputationDashboardAPIView(APIView):

    def get(self, request):

        from django.db.models import Avg
        from restapi.models.reputation import ReviewRequest, Review, ReviewRequestLead

        total_requests = ReviewRequest.objects.count()
        total_sent_requests = ReviewRequestLead.objects.filter(request_sent=True).count()

        total_reviews = Review.objects.count()

        avg_rating = Review.objects.aggregate(
            avg_rating=Avg("rating")
        )["avg_rating"] or 0

        conversion_rate = 0
        if total_sent_requests > 0:
            conversion_rate = (total_reviews / total_sent_requests) * 100

        return Response(
            {
                "avg_rating": round(avg_rating, 1),
                "requests_sent": total_sent_requests,
                "reviews_submitted": total_reviews,
                "total_reviews": total_reviews,
                "total_requests": total_requests,
                "conversion_rate": round(conversion_rate, 1),
            }
        )


class TicketReplyAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Send an email reply for a ticket with optional CC and BCC",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["subject", "message", "to"],
            properties={
                "subject": openapi.Schema(type=openapi.TYPE_STRING),
                "message": openapi.Schema(type=openapi.TYPE_STRING),
                "to": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
                ),
                "cc": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
                ),
                "bcc": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
                ),
                "sent_by": openapi.Schema(type=openapi.TYPE_INTEGER, description="Employee ID"),
            },
        ),
        responses={
            201: TicketReplySerializer,
            400: "Validation Error",
            404: "Ticket Not Found",
            500: "Internal Server Error",
        },
        tags=["Tickets"],
    )
    def post(self, request, ticket_id):
        try:
            ticket = Ticket.objects.filter(
                id=ticket_id,
                is_deleted=False,
            ).first()

            if not ticket:
                return Response(
                    {"error": "Ticket not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TicketReplyWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            sent_by = None
            sent_by_id = data.get("sent_by")
            if sent_by_id:
                sent_by = Employee.objects.filter(id=sent_by_id).first()

            reply = send_ticket_reply_service(
                ticket=ticket,
                subject=data["subject"],
                message=data["message"],
                to_emails=data["to"],
                cc_emails=data.get("cc", []),
                bcc_emails=data.get("bcc", []),
                sent_by=sent_by,
            )

            return Response(
                TicketReplySerializer(reply).data,
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as validation_error:
            logger.warning(f"Ticket Reply validation failed: {validation_error.detail}")
            return Response(
                {"error": validation_error.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error("Ticket Reply API Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



class LoginProxyAPIView(APIView):

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            resp = requests.post(
                settings.STAGE_LOGIN_URL,
                json={
                    "username": username,
                    "password": password
                },
                timeout=10
            )

            data = resp.json()

            # Pass through error from external API
            if resp.status_code != 200:
                return Response(data, status=resp.status_code)

            # Return only required data
            return Response(
                {
                    "token": data.get("access"),
                    "user": {
                        "username": data.get("username"),
                        "first_name": data.get("first_name"),
                        "last_name": data.get("last_name"),
                        "email": data.get("email"),
                        "designation": data.get("designation"),
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.exceptions.Timeout:
            return Response(
                {"error": "Login service timeout"},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )

        except Exception as e:
            return Response(
                {"error": "Login failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class ProfileProxyAPIView(APIView):
    def get(self, request):
        token = request.headers.get("Authorization")

        if not token:
            return Response(
                {
                    "error": "Authorization token missing",
                    "debug": {
                        "received_headers": dict(request.headers),
                    },
                },
                status=401,
            )

        try:
            auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"

            resp = requests.get(
                settings.STAGE_PROFILE_URL,
                headers={"Authorization": auth_header},
                timeout=10,
            )

            # Safe JSON parse
            try:
                data = resp.json() if resp.content else {}
            except Exception:
                data = {"raw": resp.text}

            return Response(
                {
                    "success": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "data": data,
                    "debug": {
                        "upstream_url": settings.STAGE_PROFILE_URL,
                        "sent_auth_header": auth_header[:20] + "...",
                    },
                },
                status=resp.status_code,
            )

        except requests.exceptions.Timeout:
            return Response(
                {
                    "error": "Profile service timeout",
                    "debug": {
                        "upstream_url": settings.STAGE_PROFILE_URL,
                        "timeout": 10,
                    },
                },
                status=504,
            )

        except requests.exceptions.RequestException as e:
            return Response(
                {
                    "error": "Upstream request failed",
                    "details": str(e),
                },
                status=502,
            )

        except Exception as e:
            return Response(
                {
                    "error": "Internal server error",
                    "details": str(e),
                },
                status=500,
            )


            
class UsersProxyAPIView(APIView):

    def get(self, request):
        try:
            token = request.headers.get("Authorization")

            params = {
                "limit": request.query_params.get("limit", 10),
                "offset": request.query_params.get("offset", 0),
                "search": request.query_params.get("search", ""),
            }

            resp = requests.get(
                settings.STAGE_USERS_URL,
                headers={
                    "Authorization": token,
                },
                params=params,
                timeout=10,
            )

            return Response(resp.json(), status=resp.status_code)

        except requests.exceptions.Timeout:
            return Response(
                {"error": "Users service timeout"},
                status=504
            )

        except Exception as e:
            return Response(
                {"error": "Users fetch failed", "details": str(e)},
                status=500
            )