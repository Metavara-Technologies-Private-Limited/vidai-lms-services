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
            campaign = Campaign.objects.filter(
                fb_campaign_id=campaign_id
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
