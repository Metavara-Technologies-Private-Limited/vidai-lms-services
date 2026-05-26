# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback
import requests

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response

from restapi.models import Campaign, Clinic
from restapi.models.social_account import SocialAccount

from django.db import transaction
from rest_framework.permissions import IsAuthenticated

from restapi.serializers.campaign_serializer import (
    SocialMediaCampaignSerializer,
)

from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
)

from restapi.models.social_account import SocialAccount

from restapi.utils.clinic_scope import (
    resolve_request_clinic,
)

from restapi.services.campaign_social_post_service import (
    post_to_facebook,
    post_to_instagram,
)

logger = logging.getLogger(__name__)


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
            platform = request.query_params.get(
                "platform",
                "facebook",
            )

            lookup_field = (
                "fb_campaign_id"
                if platform == "facebook"
                else "instagram_campaign_id"
            )

            campaign = Campaign.objects.filter(
                **{lookup_field: campaign_id}
            ).first()

            if not campaign:
                return Response({
                    "error": "Campaign not found"
                }, status=404)

            social_fb = SocialAccount.objects.filter(
                clinic_id=campaign.clinic_id,
                platform="facebook",
                is_active=True,
            ).first()

            if not social_fb:
                return Response({
                    "error": "Facebook account not connected"
                }, status=400)

            token = social_fb.access_token
            ad_account_id = social_fb.account_id
            meta_campaign_id = (
                campaign.fb_campaign_id
                if platform == "facebook"
                else campaign.instagram_campaign_id
            )

            date_preset = request.query_params.get('date_preset', 'maximum')

            currency_res = requests.get(
                f"https://graph.facebook.com/v25.0/{ad_account_id}",
                params={
                    "fields": "currency",
                    "access_token": token,
                },
            )

            currency_data = currency_res.json()

            currency = currency_data.get(
                "currency",
                "USD",
            )

            r = requests.get(
                f"https://graph.facebook.com/v25.0/{meta_campaign_id}/insights",
                params={
                    "fields": "campaign_name,impressions,clicks,reach,spend,cpc,cpm,actions",
                    "date_preset": date_preset,
                    "access_token": token,
                },
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
                        "currency": currency,
                    },
                    "message": "No data yet - campaign has no spend"
                }, status=200)

            i = insights[0]
            return Response(
                {
                    "insights": {
                        "post_impressions": int(i.get("impressions", 0)),
                        "post_clicks": int(i.get("clicks", 0)),
                        "post_engaged_users": int(i.get("reach", 0)),
                        "spend": i.get("spend", "0"),
                        "reach": i.get("reach", "0"),
                        "cpc": i.get("cpc", "0"),
                        "cpm": i.get("cpm", "0"),
                        "currency": currency,
                    }
                },
                status=200,
            )

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


class FBCampaignStatusAPIView(APIView):
    """
    POST /api/fb/campaigns/<campaign_id>/status/

    Body:
    {
        "action": "enable"
    }

    OR

    {
        "action": "disable"
    }
    """

    def post(self, request, campaign_id):

        try:

            action = request.data.get("action")

            campaign = Campaign.objects.filter(id=campaign_id).first()

            if not campaign:
                return Response({"error": "Campaign not found"}, status=404)

            if not campaign.fb_campaign_id:
                return Response({"error": "Meta campaign not synced yet"}, status=400)

            social_fb = SocialAccount.objects.filter(
                clinic_id=campaign.clinic_id,
                platform="facebook",
                is_active=True,
            ).first()

            if not social_fb:
                return Response({"error": "Facebook account not connected"}, status=400)

            token = social_fb.access_token

            meta_status = "ACTIVE" if action == "enable" else "PAUSED"

            r = requests.post(
                f"https://graph.facebook.com/v19.0/{campaign.fb_campaign_id}",
                data={
                    "status": meta_status,
                    "access_token": token,
                },
            )

            data = r.json()

            if "error" in data:
                return Response({"error": data["error"]["message"]}, status=400)

            # local DB sync
            campaign.status = "live" if meta_status == "ACTIVE" else "stopped"

            campaign.is_active = meta_status == "ACTIVE"

            campaign.save()

            return Response(
                {
                    "success": True,
                    "meta_status": meta_status,
                    "local_status": campaign.status,
                }
            )

        except Exception:
            logger.error("FB Status Update Error:\n" + traceback.format_exc())

            return Response({"error": "Internal Server Error"}, status=500)


class SocialMediaOrganicPostAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:

            clinic = resolve_request_clinic(
                request,
                required=True,
            )

            payload = request.data.copy()
            payload["clinic"] = clinic.id

            serializer = SocialMediaCampaignSerializer(data=payload)

            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data

            channels = data["select_ad_accounts"]

            raw_platform_data = data.get("platform_data") or {}

            # -----------------------------------
            # Create DB Campaign
            # -----------------------------------
            campaign = Campaign.objects.create(
                clinic_id=clinic.id,
                campaign_name=data["campaign_name"],
                campaign_description=data["campaign_description"],
                campaign_objective=data["campaign_objective"],
                target_audience=data["target_audience"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                campaign_mode=Campaign.ORGANIC,
                campaign_content=data.get("campaign_content", ""),
                image_url=data.get("image_url"),
                status=data.get("status", "live"),
                is_active=data.get("is_active", True),
                enter_time=data.get("enter_time"),
                selected_start=data.get("selected_start"),
                selected_end=data.get("selected_end"),
                platform_data=raw_platform_data,
                budget_data={},
            )

            # -----------------------------------
            # Save selected platforms
            # -----------------------------------
            for platform in channels:

                CampaignSocialMediaConfig.objects.create(
                    campaign=campaign,
                    platform_name=platform,
                    is_active=True,
                )

            results = {}

            # ===================================
            # FACEBOOK ORGANIC POST
            # ===================================
            if "facebook" in channels:

                social_fb = SocialAccount.objects.filter(
                    clinic_id=clinic.id,
                    platform="facebook",
                    is_active=True,
                ).first()

                if not social_fb:

                    results["facebook"] = {
                        "success": False,
                        "error": "Facebook not connected",
                    }

                else:

                    fb_platform_data = raw_platform_data.get("facebook", {}) or {}

                    facebook_message = (
                        fb_platform_data.get("content")
                        if isinstance(fb_platform_data, dict)
                        else str(fb_platform_data)
                    )

                    fb_result = post_to_facebook(
                        page_id=social_fb.page_id,
                        page_token=social_fb.access_token,
                        message=facebook_message,
                        image_url=campaign.image_url,
                    )

                    results["facebook"] = fb_result

            # ===================================
            # INSTAGRAM ORGANIC POST
            # ===================================
            if "instagram" in channels:

                social_ig = SocialAccount.objects.filter(
                    clinic_id=clinic.id,
                    platform="facebook",
                    is_active=True,
                ).first()

                if not social_ig:

                    results["instagram"] = {
                        "success": False,
                        "error": "Instagram not connected",
                    }

                else:

                    ig_platform_data = raw_platform_data.get("instagram", {}) or {}

                    instagram_message = (
                        ig_platform_data.get("content")
                        if isinstance(ig_platform_data, dict)
                        else str(ig_platform_data)
                    )

                    ig_result = post_to_instagram(
                        ig_user_id=social_ig.org_urn,
                        access_token=social_ig.access_token,
                        message=instagram_message,
                        image_url=campaign.image_url,
                    )

                    results["instagram"] = ig_result

            return Response(
                {
                    "success": True,
                    "campaign_id": str(campaign.id),
                    "results": results,
                },
                status=201,
            )

        except Exception as e:

            logger.error("Organic Social Post Error:\n" + traceback.format_exc())

            return Response(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )

