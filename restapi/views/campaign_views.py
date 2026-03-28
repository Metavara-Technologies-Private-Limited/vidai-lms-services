# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback
import requests

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError

from drf_yasg.utils import swagger_auto_schema
from restapi.services.campaign_social_post_service import get_facebook_post_insights
from restapi.models import Campaign
from restapi.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignReadSerializer,
)
from restapi.serializers.campaign_social_post_serializer import (
    CampaignSocialPostCallbackSerializer
)
import requests
from restapi.services.zapier_service import send_to_zapier
from restapi.services.mailchimp_service import get_mailchimp_campaign_report
from restapi.services.campaign_social_post_service import handle_zapier_callback
from restapi.services.campaign_social_post_service import get_facebook_post_insights
from restapi.models.social_account import SocialAccount

logger = logging.getLogger(__name__)


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