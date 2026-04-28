# =====================================================
# restapi/views/webhook_views.py
# =====================================================

from django.utils import timezone
import logging
import traceback

from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Lead, Clinic
from restapi.models.campaign import Campaign
from restapi.serializers.campaign_social_post_serializer import (
    CampaignSocialPostCallbackSerializer,
)
from restapi.serializers.mailchimp_serializer import (
    MailchimpWebhookSerializer,
)

from restapi.services.zapier_service import send_to_zapier
from restapi.services.mailchimp_service import create_mailchimp_event

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# LINKEDIN ZAPIER CALLBACK
# -------------------------------------------------------------------
class LinkedInZapierCallbackAPIView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Zapier callback to update LinkedIn campaign state",
        request_body=CampaignSocialPostCallbackSerializer,
        responses={
            200: "Success",
            400: "Validation Error",
            404: "Campaign Not Found",
        },
        tags=["Webhooks"],
    )
    def post(self, request):
        payload = request.data

        try:
            action = payload.get("action")

            valid_actions = {
                None,
                "STATUS_SYNC",
                "UPDATE_SYNC",
                "INSIGHTS_SYNC",
            }

            if action not in valid_actions:
                return Response(
                    {
                        "error": "Unknown action",
                        "action": action,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            campaign_id = payload.get("internal_campaign_uuid")

            if not campaign_id:
                return Response(
                    {
                        "error": "internal_campaign_uuid is required"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                campaign = Campaign.objects.get(id=campaign_id)
            except Campaign.DoesNotExist:
                return Response(
                    {
                        "error": "Campaign not found",
                        "campaign_id": campaign_id,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # ------------------------------------------------------
            # STATUS SYNC
            # ------------------------------------------------------
            if action == "STATUS_SYNC":
                campaign.linkedin_live_status = payload.get(
                    "linkedin_status"
                )

                campaign.modified_at = timezone.now()

                campaign.save(
                    update_fields=[
                        "linkedin_live_status",
                        "modified_at",
                    ]
                )

                return Response(
                    {
                        "status": "provider_status_saved",
                        "linkedin_status": campaign.linkedin_live_status,
                    },
                    status=status.HTTP_200_OK,
                )

            # ------------------------------------------------------
            # UPDATE SYNC
            # ------------------------------------------------------
            if action == "UPDATE_SYNC":
                new_status = payload.get("linkedin_status")

                campaign.linkedin_live_status = new_status

                if new_status == "ACTIVE":
                    campaign.status = Campaign.Status.LIVE

                elif new_status == "PAUSED":
                    campaign.status = Campaign.Status.PAUSED

                elif new_status == "COMPLETED":
                    campaign.status = Campaign.Status.COMPLETED

                elif new_status == "STOPPED":
                    campaign.status = Campaign.Status.STOPPED

                campaign.modified_at = timezone.now()

                campaign.save(
                    update_fields=[
                        "linkedin_live_status",
                        "status",
                        "modified_at",
                    ]
                )

                return Response(
                    {
                        "status": "update_synced",
                        "linkedin_status": new_status,
                        "campaign_id": str(campaign.id),
                    },
                    status=status.HTTP_200_OK,
                )

            # ------------------------------------------------------
            # INSIGHTS SYNC
            # ------------------------------------------------------
            if action == "INSIGHTS_SYNC":
                campaign.last_synced_metrics = {
                    "campaign_metrics": payload.get(
                        "metrics",
                        {},
                    ),
                    "ads": payload.get(
                        "ads",
                        [],
                    ),
                }

                campaign.last_metrics_synced_at = timezone.now()
                campaign.modified_at = timezone.now()

                campaign.save(
                    update_fields=[
                        "last_synced_metrics",
                        "last_metrics_synced_at",
                        "modified_at",
                    ]
                )

                return Response(
                    {
                        "status": "metrics_saved",
                        "campaign_id": str(campaign.id),
                    },
                    status=status.HTTP_200_OK,
                )

            # ------------------------------------------------------
            # DEFAULT = LINKEDIN CREATE ACK
            # ------------------------------------------------------
            campaign_urn = payload.get("campaign_urn")
            creative_urn = payload.get("creative_urn")

            if campaign_urn:
                campaign.linkedin_campaign_urn = campaign_urn
                campaign.linkedin_external_campaign_id = (
                    campaign_urn.split(":")[-1]
                )

            if creative_urn:
                campaign.linkedin_creative_urn = creative_urn
                campaign.linkedin_creative_id = (
                    creative_urn.split(":")[-1]
                )

            account_id = payload.get("account_id")
            if account_id:
                campaign.linkedin_account_id = account_id

            post_urn = payload.get("post_urn")
            if post_urn:
                campaign.linkedin_post_urn = post_urn

            campaign_group_urn = payload.get(
                "campaign_group_urn"
            )
            if campaign_group_urn:
                campaign.linkedin_campaign_group_urn = (
                    campaign_group_urn
                )

            ads_manager_url = payload.get(
                "ads_manager_url"
            )
            if ads_manager_url:
                campaign.linkedin_ads_manager_url = (
                    ads_manager_url
                )

            campaign.linkedin_raw_response = payload
            campaign.status = Campaign.Status.SCHEDULED
            campaign.modified_at = timezone.now()

            campaign.save(
                update_fields=[
                    "linkedin_campaign_urn",
                    "linkedin_external_campaign_id",
                    "linkedin_creative_urn",
                    "linkedin_creative_id",
                    "linkedin_account_id",
                    "linkedin_post_urn",
                    "linkedin_campaign_group_urn",
                    "linkedin_ads_manager_url",
                    "linkedin_raw_response",
                    "status",
                    "modified_at",
                ]
            )

            return Response(
                {
                    "status": "success",
                    "campaign_id": str(campaign.id),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(
                "LinkedIn callback error:\n" + traceback.format_exc()
            )
            return Response(
                {
                    "error": str(e),
                    "payload": request.data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


# =====================================================
# GOHIGHLEVEL LEAD WEBHOOK
# =====================================================
class GoHighLevelLeadWebhookAPIView(APIView):

    def post(self, request):
        try:
            data = request.data
            logger.info(f"GHL webhook received: {data}")

            first_name = (
                data.get("first_name")
                or data.get("contact_first_name")
                or ""
            )
            last_name = (
                data.get("last_name")
                or data.get("contact_last_name")
                or ""
            )

            full_name = f"{first_name} {last_name}".strip()

            if not full_name:
                full_name = (
                    data.get("contact_name")
                    or data.get("name")
                    or data.get("full_name")
                    or data.get("contact_full_name")
                    or "GHL Lead"
                )

            email = (
                data.get("email")
                or data.get("contact_email")
                or ""
            )

            phone = (
                data.get("phone")
                or data.get("phone_number")
                or data.get("contact_phone")
                or ""
            )

            location = (
                data.get("city")
                or data.get("state")
                or data.get("country")
                or data.get("address1")
                or ""
            )

            full_name = (full_name or "GHL Lead")[:255]
            email = email[:254]
            phone = phone[:20]
            location = location[:255]

            clinic = Clinic.objects.first()
            if not clinic:
                return Response(
                    {"error": "No clinic found"},
                    status=400,
                )

            from restapi.models import Department

            department = Department.objects.filter(
                clinic=clinic
            ).first()

            if not department:
                return Response(
                    {
                        "error": "No department found"
                    },
                    status=400,
                )

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

            send_to_zapier(
                {
                    "event": "lead_created",
                    "lead_id": str(lead.id),
                    "clinic_id": lead.clinic.id,
                    "full_name": lead.full_name,
                    "contact_no": lead.contact_no,
                    "email": lead.email,
                    "lead_status": lead.lead_status,
                    "source": "facebook",
                    "location": location,
                }
            )

            return Response(
                {
                    "status": "lead_created",
                    "lead_id": str(lead.id),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception:
            logger.error(
                "GHL webhook error:\n" + traceback.format_exc()
            )
            return Response(
                {
                    "error": "Internal Server Error"
                },
                status=500,
            )


# -------------------------------------------------------------------
# MAILCHIMP WEBHOOK
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
            serializer = MailchimpWebhookSerializer(
                data=request.data
            )
            serializer.is_valid(raise_exception=True)

            create_mailchimp_event(
                serializer.validated_data
            )

            return Response(
                {
                    "message": (
                        "Mailchimp event stored successfully"
                    )
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.error(
                "Mailchimp webhook error:\n"
                + traceback.format_exc()
            )

            return Response(
                {
                    "error": "Internal Server Error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
