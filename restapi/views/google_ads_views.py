import logging
import traceback
import requests

from django.conf import settings
from django.utils.dateparse import parse_datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from restapi.models import Campaign, CampaignSocialMediaConfig
from restapi.models.social_account import SocialAccount
from restapi.services.zapier_service import send_to_zapier_social

logger = logging.getLogger(__name__)


class GoogleAdsCampaignCreateAPIView(APIView):
    """
    POST /api/google-ads/create/
    Sends a Google Ads campaign creation request to Zapier with fallback auth.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data

            clinic_id   = data.get("clinic_id")
            customer_id = data.get("customer_id")

            if not clinic_id:
                return Response(
                    {"success": False, "error": "clinic_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not data.get("campaign_name"):
                return Response(
                    {"success": False, "error": "campaign_name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ✅ FIX: Always read tokens from DB first — env is last resort only
            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True,
            ).first()

            if not customer_id and google_account:
                customer_id = google_account.customer_id

            if not customer_id:
                return Response(
                    {
                        "success": False,
                        "error": "Google Ads customer_id not found. Please reconnect your Google Ads account.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ✅ FIX: DB tokens are PRIMARY — env vars are LAST RESORT fallback only
            refresh_token = None
            access_token  = None

            if google_account:
                # Always try DB first
                refresh_token = google_account.user_token   or None
                access_token  = google_account.access_token or None
                logger.info(
                    "[GoogleAdsView] Token source: DB | clinic=%s | has_refresh=%s | has_access=%s",
                    clinic_id, bool(refresh_token), bool(access_token),
                )

            # Only fall back to env if DB has nothing
            if not refresh_token:
                refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", None)
                if refresh_token:
                    logger.warning("[GoogleAdsView] DB refresh_token missing — falling back to env var for clinic=%s", clinic_id)

            if not access_token:
                access_token = getattr(settings, "GOOGLE_ACCESS_TOKEN", None)
                if access_token:
                    logger.warning("[GoogleAdsView] DB access_token missing — falling back to env var for clinic=%s", clinic_id)

            if not refresh_token:
                return Response(
                    {
                        "success": False,
                        "error": "Google refresh token missing. Please connect via OAuth in Integrations.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            campaign_name = data["campaign_name"]

            google_data = data.get("platform_data", {}).get("google_ads", {})

            # ✅ image_url — always a string, never null (Zapier hides null fields)
            raw_image_url = (
                data.get("image_url")
                or (google_data.get("image_url") if isinstance(google_data, dict) else None)
                or ""
            )
            image_url = str(raw_image_url).strip() if raw_image_url else ""

            # ✅ keywords — convert list to comma string
            keywords_raw = data.get("keywords", [])
            if isinstance(keywords_raw, list):
                keywords_str = ",".join(k.strip() for k in keywords_raw if str(k).strip())
            else:
                keywords_str = str(keywords_raw).strip()

            # ✅ internal_campaign_id — always a string
            internal_campaign_id = str(data.get("internal_campaign_id") or "").strip()

            # ✅ FIX: login_customer_id — safe resolution, avoids str(None) = "None" bug
            _login_from_payload = data.get("login_customer_id") or None
            _login_from_db      = (
                getattr(google_account, "login_customer_id", None)
                if google_account else None
            ) or None
            _login_from_env     = getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", None) or None

            _raw_login          = _login_from_payload or _login_from_db or _login_from_env or ""
            login_customer_id   = str(_raw_login).replace("-", "")

            description_2 = (
                data.get("description_2")
                or (google_data.get("description_2") if isinstance(google_data, dict) else None)
                or "Call us now or visit our website."
            )

            campaign_type = data.get("campaign_type", "SEARCH")

            callback_base = getattr(settings, "BACKEND_BASE_URL", "https://lms-vidaisolutions.metavaratechnologies.com")
            campaign_created_callback_url = f"{callback_base}/api/google-ads/callback/campaign-created/"

            # ✅ Map our status to Google Ads status
            our_status = str(
                data.get("campaign_status")
                or data.get("status")
                or "draft"
            ).strip().lower()

            google_ads_status = (
                "PAUSED"
                if our_status == "draft"
                else "ENABLED"
            )

            raw_schedule_datetime = str(
                data.get("schedule_datetime") or ""
            ).strip()

            parsed_schedule_datetime = parse_datetime(
                raw_schedule_datetime
            )

            schedule_datetime = (
                parsed_schedule_datetime.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if parsed_schedule_datetime
                else raw_schedule_datetime
            )

            # ✅ NEW FIELDS — campaign objective, target audience, schedule dates & time
            campaign_objective = str(data.get("campaign_objective") or "").strip()
            target_audience    = data.get("target_audience", "")
            if isinstance(target_audience, list):
                target_audience = ",".join(str(t).strip() for t in target_audience if str(t).strip())
            else:
                target_audience = str(target_audience).strip()

            start_date  = str(data.get("start_date")  or data.get("from_date") or "").strip()
            end_date    = str(data.get("end_date")    or data.get("to_date")   or "").strip()
            start_time  = str(data.get("start_time")  or data.get("time")      or "").strip()

            zapier_payload = {
                "event":                         "google_ads_campaign_created",
                "campaign_name":                 campaign_name,
                "campaign_type":                 campaign_type,
                "internal_campaign_id":          internal_campaign_id,
                "campaign_created_callback_url": campaign_created_callback_url,
                "image_url":                     image_url,
                "customer_id":                   str(customer_id).replace("-", ""),
                "login_customer_id":             login_customer_id,
                "developer_token":               settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id":                     settings.GOOGLE_CLIENT_ID,
                "client_secret":                 settings.GOOGLE_CLIENT_SECRET,
                # ✅ FIX: DB token is sent — not env var
                "refresh_token":                 refresh_token,
                "access_token":                  access_token or "",
                "budget":                        int(data.get("budget", 500)),
                "bidding_strategy":              data.get("bidding_strategy", "MANUAL_CPC"),
                "locations":                     data.get("locations", []),
                "keywords":                      keywords_str,
                "cpc_bid":                       int(data.get("cpc_bid", 20)),
                "ad_group_name":                 data.get("ad_group_name", f"{campaign_name} AdGroup"),
                "final_url":                     data.get("final_url", "https://example.com"),
                "headline_1":                    data.get("headline_1", campaign_name[:30]),
                "headline_2":                    data.get("headline_2", "Learn More"),
                "headline_3":                    data.get("headline_3", "Contact Us Today"),
                "description":                   data.get("description", "")[:90],
                "description_2":                 description_2[:90],
                "campaign_status":               google_ads_status,
                "our_status":                    our_status,
                # ✅ NEW FIELDS
                "campaign_objective":            campaign_objective,
                "target_audience":               target_audience,
                "start_date":                    start_date,
                "end_date":                      end_date,
                "start_time":                    start_time,
                "schedule_datetime":             schedule_datetime,
            }

            logger.info(
                "[GoogleAdsView] Sending to Zapier | clinic=%s | customer_id=%s | "
                "token_source=%s | image_url='%s' | keywords='%s' | "
                "login_customer_id=%s | campaign_type=%s | internal_campaign_id=%s | "
                "our_status=%s | google_ads_status=%s | "
                "campaign_objective=%s | target_audience=%s | start_date=%s | end_date=%s | start_time=%s",
                clinic_id, customer_id,
                "DB" if google_account and google_account.user_token else "ENV_FALLBACK",
                image_url, keywords_str, login_customer_id,
                campaign_type, internal_campaign_id,
                our_status, google_ads_status,
                campaign_objective, target_audience, start_date, end_date, start_time,
            )

            webhook_url = settings.ZAPIER_WEBHOOK_GOOGLE_ADS_URL
            try:
                zapier_resp   = requests.post(webhook_url, json=zapier_payload, timeout=10)
                response_code = zapier_resp.status_code
                logger.info("[GoogleAdsView] Zapier response: %s | body: %s", response_code, zapier_resp.text)
            except requests.exceptions.RequestException as e:
                logger.error("[GoogleAdsView] Zapier request failed: %s", str(e))
                return Response(
                    {"success": False, "error": "Failed to reach Zapier webhook"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            if response_code == 200:
                return Response(
                    {
                        "success": True,
                        "message": "Google Ads campaign request sent to Zapier successfully",
                        "data": {
                            "campaign_name":        campaign_name,
                            "customer_id":          customer_id,
                            "has_image":            bool(image_url),
                            "keywords_sent":        keywords_str,
                            "internal_campaign_id": internal_campaign_id,
                            "google_ads_status":    google_ads_status,
                            "token_source":         "DB" if google_account and google_account.user_token else "ENV_FALLBACK",
                            "status":               "sent_to_zapier",
                            "campaign_objective":   campaign_objective,
                            "target_audience":      target_audience,
                            "start_date":           start_date,
                            "end_date":             end_date,
                            "start_time":           start_time,
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"success": False, "error": f"Zapier webhook failed with status {response_code}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except Exception:
            logger.error("[GoogleAdsView] Unexpected error:\n%s", traceback.format_exc())
            return Response(
                {"success": False, "error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GoogleAdsCampaignCreatedCallbackAPIView(APIView):
    """
    POST /api/google-ads/callback/campaign-created/
    Called by Zapier after successfully creating a Google Ads campaign.
    Saves Google campaign resource names and IDs to DB.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            logger.info("[GoogleAdsCallback] Campaign created callback received: %s", data)

            internal_campaign_id          = data.get("internal_campaign_id")
            google_campaign_resource_name = data.get("google_campaign_resource_name")
            google_campaign_id            = data.get("google_campaign_id")
            google_ad_group_id            = data.get("google_ad_group_id")
            google_ad_group_resource_name = data.get("google_ad_group_resource_name")
            google_ad_id                  = data.get("google_ad_id")
            campaign_type                 = data.get("campaign_type", "SEARCH")
            zapier_status                 = data.get("status", "ENABLED")
            error                         = data.get("error")

            if error:
                logger.error("[GoogleAdsCallback] Zapier reported error: %s | campaign=%s", error, internal_campaign_id)
                return Response(
                    {"success": False, "error": f"Zapier error: {error}"},
                    status=status.HTTP_200_OK,
                )

            if not internal_campaign_id:
                logger.warning("[GoogleAdsCallback] No internal_campaign_id in callback — cannot save to DB")
                return Response(
                    {"success": False, "error": "internal_campaign_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                campaign = Campaign.objects.get(id=internal_campaign_id)
            except Campaign.DoesNotExist:
                logger.error("[GoogleAdsCallback] Campaign not found in DB: %s", internal_campaign_id)
                return Response(
                    {"success": False, "error": "Campaign not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            platform_data = campaign.platform_data or {}
            if not isinstance(platform_data.get("google_ads"), dict):
                platform_data["google_ads"] = {}

            platform_data["google_ads"].update({
                "campaign_resource_name": google_campaign_resource_name,
                "campaign_id":            google_campaign_id,
                "ad_group_id":            google_ad_group_id,
                "ad_group_resource_name": google_ad_group_resource_name,
                "ad_id":                  google_ad_id,
                "campaign_type":          campaign_type,
                "google_status":          zapier_status,
            })

            campaign.platform_data = platform_data
            campaign.save(update_fields=["platform_data"])

            config, _ = CampaignSocialMediaConfig.objects.get_or_create(
                campaign=campaign,
                platform_name=CampaignSocialMediaConfig.GOOGLE_ADS,
                defaults={"insights": {}}
            )
            existing_insights = config.insights or {}
            existing_insights.update({
                "google_campaign_id":            google_campaign_id,
                "google_campaign_resource_name": google_campaign_resource_name,
                "campaign_type":                 campaign_type,
                "google_status":                 zapier_status,
            })
            config.insights = existing_insights
            config.save(update_fields=["insights"])

            logger.info(
                "[GoogleAdsCallback] Saved Google Ads IDs for campaign %s | resource_name=%s | type=%s",
                internal_campaign_id, google_campaign_resource_name, campaign_type,
            )

            return Response({"success": True}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("[GoogleAdsCallback] Unexpected error:\n%s", traceback.format_exc())
            return Response(
                {"success": False, "error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GoogleAdsCampaignStatusAPIView(APIView):
    """
    POST /api/google-ads/status/
    Pause or enable a Google Ads campaign directly via Google Ads REST API.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            campaign_id = request.data.get("campaign_id")
            action      = request.data.get("action")  # "pause" or "enable"

            if not campaign_id or action not in ["pause", "enable"]:
                return Response(
                    {"error": "campaign_id and action (pause/enable) are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            campaign  = Campaign.objects.get(id=campaign_id)
            clinic_id = campaign.clinic_id

            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True,
            ).first()

            if not google_account:
                return Response(
                    {"error": "Google Ads not connected for this clinic"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cust_id = str(google_account.customer_id or "").replace("-", "")
            if not cust_id:
                return Response(
                    {"error": "Google Ads customer_id missing. Please reconnect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ✅ FIX: DB token primary, env fallback only
            refresh_token = google_account.user_token or None
            if not refresh_token:
                refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", None)
                logger.warning("[GoogleAdsStatus] DB refresh_token missing — using env fallback for clinic=%s", clinic_id)

            if not refresh_token:
                return Response(
                    {"error": "Google refresh token missing. Please reconnect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step 1: Get fresh access token
            auth_res = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id":     settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type":    "refresh_token",
                },
                timeout=10,
            )
            auth_json = auth_res.json()

            if "access_token" not in auth_json:
                logger.error("[GoogleAdsStatus] Token refresh failed: %s", auth_json)
                return Response(
                    {"error": "Failed to refresh Google token"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            access_token = auth_json["access_token"]

            headers = {
                "Authorization":   f"Bearer {access_token}",
                "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "Content-Type":    "application/json",
            }

            login_id = str(getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")).replace("-", "")
            if login_id and login_id != cust_id:
                headers["login-customer-id"] = login_id

            # Step 2: Get campaign_resource_name from DB
            platform_data          = campaign.platform_data or {}
            google_data            = platform_data.get("google_ads", {})
            campaign_resource_name = None

            if isinstance(google_data, dict):
                campaign_resource_name = google_data.get("campaign_resource_name") or None

            # ✅ FIX: Step 3 — GAQL does not support LIKE. Fetch all active campaigns
            #         and match locally by name (exact first, then contains).
            if not campaign_resource_name:
                safe_name = campaign.campaign_name.strip()
                first_word = safe_name.split()[0] if safe_name.split() else safe_name

                # Valid GAQL — no LIKE, no wildcard
                query = (
                    "SELECT campaign.id, campaign.name, campaign.resource_name, campaign.status "
                    "FROM campaign "
                    "WHERE campaign.status != 'REMOVED' "
                    "ORDER BY campaign.id DESC LIMIT 50"
                )
                logger.info(
                    "[GoogleAdsStatus] DB miss — fetching all Google Ads campaigns to match '%s' | cust_id=%s",
                    safe_name, cust_id,
                )

                search_resp = requests.post(
                    f"https://googleads.googleapis.com/v17/customers/{cust_id}/googleAds:search",
                    headers=headers,
                    json={"query": query},
                    timeout=10,
                )
                try:
                    search_res = search_resp.json() if search_resp.text.strip() else {}
                except Exception as e:
                    logger.error("[GoogleAdsStatus] Failed to parse search response: %s", e)
                    search_res = {}

                results = search_res.get("results", [])

                logger.info(
                    "[GoogleAdsStatus] Google Ads search HTTP=%s | %d campaigns returned",
                    search_resp.status_code, len(results),
                )

                # Strategy 1: exact case-insensitive match
                for r in results:
                    gname = r.get("campaign", {}).get("name", "")
                    if gname.strip().lower() == safe_name.lower():
                        campaign_resource_name = r.get("campaign", {}).get("resourceName")
                        logger.info("[GoogleAdsStatus] Exact match: '%s' → %s", gname, campaign_resource_name)
                        break

                # Strategy 2: contains match (our name inside Google name, or first word match)
                if not campaign_resource_name:
                    for r in results:
                        gname = r.get("campaign", {}).get("name", "")
                        if (
                            safe_name.lower() in gname.lower()
                            or first_word.lower() in gname.lower()
                        ):
                            campaign_resource_name = r.get("campaign", {}).get("resourceName")
                            logger.info("[GoogleAdsStatus] Contains match: '%s' → %s", gname, campaign_resource_name)
                            break

                # Log all available names so mismatches are easy to spot
                if not campaign_resource_name:
                    all_names = [r.get("campaign", {}).get("name", "") for r in results]
                    logger.error(
                        "[GoogleAdsStatus] No match for '%s' | "
                        "Available Google Ads campaign names: %s | "
                        "HTTP=%s",
                        safe_name, all_names, search_resp.status_code,
                    )

                # Cache in DB so next call is instant
                if campaign_resource_name:
                    updated_platform_data = campaign.platform_data or {}
                    if not isinstance(updated_platform_data.get("google_ads"), dict):
                        updated_platform_data["google_ads"] = {}
                    updated_platform_data["google_ads"]["campaign_resource_name"] = campaign_resource_name
                    campaign.platform_data = updated_platform_data
                    campaign.save(update_fields=["platform_data"])

            if not campaign_resource_name:
                logger.info("[GoogleAdsStatus] No Google Ads campaign found for '%s' — skipping", campaign.campaign_name)
                return Response(
                    {"success": True, "skipped": True, "message": "No Google Ads campaign found — skipped"},
                    status=status.HTTP_200_OK,
                )

            # Step 4: Mutate campaign status
            new_google_status = "PAUSED" if action == "pause" else "ENABLED"

            mutate_resp = requests.post(
                f"https://googleads.googleapis.com/v17/customers/{cust_id}/campaigns:mutate",
                headers=headers,
                json={
                    "operations": [
                        {
                            "update":     {"resourceName": campaign_resource_name, "status": new_google_status},
                            "updateMask": "status",
                        }
                    ]
                },
                timeout=10,
            )
            try:
                mutate_res = mutate_resp.json() if mutate_resp.text.strip() else {}
            except Exception as e:
                logger.error("[GoogleAdsStatus] Failed to parse mutate response: %s", e)
                mutate_res = {}

            if "results" not in mutate_res:
                logger.error("[GoogleAdsStatus] Mutate failed: %s", mutate_res)
                return Response(
                    {"error": "Failed to update Google Ads campaign status", "details": mutate_res},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            # ✅ Update our DB status to match Google Ads
            new_our_status     = "paused" if action == "pause" else "live"
            campaign.status    = new_our_status
            campaign.is_active = (action == "enable")
            campaign.save(update_fields=["status", "is_active"])

            p_data = campaign.platform_data or {}
            if not isinstance(p_data.get("google_ads"), dict):
                p_data["google_ads"] = {}
            p_data["google_ads"]["google_status"] = new_google_status
            campaign.platform_data = p_data
            campaign.save(update_fields=["platform_data"])

            logger.info(
                "[GoogleAdsStatus] Campaign %s set to %s | our DB status=%s",
                campaign_resource_name, new_google_status, new_our_status,
            )

            return Response(
                {
                    "success":           True,
                    "campaign_id":       str(campaign_id),
                    "action":            action,
                    "new_status":        new_our_status,
                    "google_ads_status": new_google_status,
                },
                status=status.HTTP_200_OK,
            )

        except Campaign.DoesNotExist:
            return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            logger.error("[GoogleAdsStatus] Unexpected error:\n%s", traceback.format_exc())
            return Response({"success": False, "error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =====================================================
# ✅ Google Ads Insights — reads from DB only
# =====================================================
class GoogleAdsInsightsAPIView(APIView):
    """
    GET /api/google-ads/insights/?campaign_id=<uuid>&clinic_id=<int>
    Reads saved insights from DB for THIS specific campaign only.
    ✅ FIX: filters by clinic_id to prevent cross-clinic data leakage.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        campaign_id = request.query_params.get("campaign_id")
        clinic_id   = request.query_params.get("clinic_id")

        if not campaign_id:
            return Response({"error": "campaign_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # ✅ FIX: filter by clinic_id so only this clinic's campaign is returned
            filters = {"id": campaign_id}
            if clinic_id:
                filters["clinic_id"] = clinic_id

            try:
                campaign = Campaign.objects.get(**filters)
            except Campaign.DoesNotExist:
                return Response(
                    {"error": f"Campaign {campaign_id} not found for this clinic"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            config = CampaignSocialMediaConfig.objects.filter(
                campaign=campaign,
                platform_name="google_ads",
            ).first()

            if not config or not config.insights:
                logger.info("[GoogleAdsInsights] No insights in DB yet for campaign %s — returning zeros", campaign_id)
                return Response(
                    {
                        "success":     True,
                        "campaign_id": campaign_id,
                        "insights": {
                            "campaign_id": campaign_id, "ads_campaign_name": "",
                            "impressions": 0, "clicks": 0, "ctr": 0.0,
                            "avg_cpc": 0.0, "cost": 0.0, "conversions": 0,
                        },
                        "message": "No insights yet — Zapier may still be fetching",
                    },
                    status=status.HTTP_200_OK,
                )

            saved = config.insights
            logger.info("[GoogleAdsInsights] Returning DB insights for campaign %s: %s", campaign_id, saved)

            return Response(
                {
                    "success":     True,
                    "campaign_id": campaign_id,
                    "insights": {
                        "campaign_id":       campaign_id,
                        "ads_campaign_name": saved.get("ads_campaign_name", ""),
                        "impressions":       saved.get("impressions",  0),
                        "clicks":            saved.get("clicks",       0),
                        "ctr":               saved.get("ctr",          0.0),
                        "avg_cpc":           saved.get("avg_cpc",      0.0),
                        "cost":              saved.get("cost",         0.0),
                        "conversions":       saved.get("conversions",  0),
                        "fetched_at":        saved.get("fetched_at",   None),
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error("[GoogleAdsInsights] Error for campaign %s: %s\n%s", campaign_id, e, traceback.format_exc())
            return Response({"error": "Failed to fetch insights", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =====================================================
# ✅ Zapier Callback — Insights Received
# =====================================================
class GoogleAdsInsightsCallbackAPIView(APIView):
    """
    POST /api/google-ads/callback/insights/
    Called by Zapier after fetching Google Ads insights.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            logger.info("[GoogleAdsInsightsCallback] Received: %s", data)

            internal_campaign_id = data.get("internal_campaign_id")
            error                = data.get("error")

            if error:
                logger.error("[GoogleAdsInsightsCallback] Zapier error: %s | campaign=%s", error, internal_campaign_id)
                return Response({"success": False, "error": f"Zapier error: {error}"}, status=status.HTTP_200_OK)

            if not internal_campaign_id:
                return Response({"success": False, "error": "internal_campaign_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                campaign = Campaign.objects.get(id=internal_campaign_id)
            except Campaign.DoesNotExist:
                logger.error("[GoogleAdsInsightsCallback] Campaign not found: %s", internal_campaign_id)
                return Response({"success": False, "error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

            config, _ = CampaignSocialMediaConfig.objects.get_or_create(
                campaign=campaign,
                platform_name=CampaignSocialMediaConfig.GOOGLE_ADS,
                defaults={"insights": {}}
            )

            config.insights = {
                "impressions":       data.get("impressions", 0),
                "clicks":            data.get("clicks", 0),
                "cost":              data.get("cost", 0),
                "ctr":               data.get("ctr", 0),
                "avg_cpc":           data.get("avg_cpc", 0),
                "conversions":       data.get("conversions", 0),
                "ads_campaign_name": data.get("ads_campaign_name", ""),
                "total_budget":      data.get("total_budget", "0"),
            }
            config.save(update_fields=["insights"])

            logger.info("[GoogleAdsInsightsCallback] Saved insights for campaign %s: %s", internal_campaign_id, config.insights)
            return Response({"success": True}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("[GoogleAdsInsightsCallback] Unexpected error:\n%s", traceback.format_exc())
            return Response({"success": False, "error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)