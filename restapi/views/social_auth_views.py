import logging
import os
import json
import base64
import secrets
import traceback
import urllib.parse
from datetime import datetime, timedelta
import logging
import requests

from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from django.utils import timezone
from restapi.models import Clinic, Campaign
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

from restapi.models import Clinic, Campaign
from restapi.models.social_account import SocialAccount
from restapi.utils.linkedin import (
    create_campaign_group,
    fetch_linkedin_account_details,
)
from restapi.utils.clinic_scope import resolve_request_clinic
from restapi.utils.clinic_scope import resolve_request_clinic


logger = logging.getLogger(__name__)


# =====================================================
# LINKEDIN AUTH
# =====================================================

class LinkedInLoginAPIView(APIView):
    def get(self, request):
        clinic_id = request.GET.get("clinic_id")

        if clinic_id:
            state_payload = base64.urlsafe_b64encode(
                json.dumps({"clinic_id": clinic_id}).encode()
            ).decode()

        scopes = [
            "openid",
            "profile",
            "email",

            # Ads
            "r_ads",
            "rw_ads",
            "r_ads_reporting",

            # Organization / social analytics
            "r_organization_admin",
            "rw_organization_admin",
            "r_organization_social",
            "w_organization_social",

            # Optional if posting as member
            "w_member_social",

            # Optional basic profile legacy
            "r_basicprofile",

            # Optional
            "r_1st_connections_size",
        ]

        scope_param = "%20".join(scopes)

        auth_url = (
            "https://www.linkedin.com/oauth/v2/authorization"
            "?response_type=code"
            f"&client_id={settings.LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
            f"&scope={scope_param}"
            f"&state={state_payload}"
            "&prompt=login"
        )

        return redirect(auth_url)


class LinkedInCallbackAPIView(APIView):
    def get(self, request):
        code = request.GET.get("code")
        error = request.GET.get("error")

        if error:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&error={error}"
            )

        token_response = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            },
        )

        token_data = token_response.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        if not access_token:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=token_exchange_failed"
            )

        expires_at = None
        if expires_in:
            expires_at = timezone.now() + timedelta(
                seconds=expires_in
            )

        linkedin_details = fetch_linkedin_account_details(
            access_token
        )

        if not linkedin_details:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=no_ad_account"
            )

        state_raw = request.GET.get("state")

        clinic_id = None
        if state_raw:
            try:
                state_data = json.loads(
                    base64.urlsafe_b64decode(state_raw).decode()
                )
                clinic_id = state_data.get("clinic_id")
            except Exception:
                pass

        if not clinic_id:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=missing_clinic"
            )

        clinic = Clinic.objects.filter(id=clinic_id).first()

        if not clinic:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=invalid_clinic"
            )

        if not clinic:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=no_clinic"
            )

        existing = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin",
        ).first()

        campaign_group_urn = None

        if existing and existing.campaign_group:
            campaign_group_urn = existing.campaign_group
        else:
            campaign_group_urn = create_campaign_group(
                access_token,
                linkedin_details["account_id"],
            )

            if not campaign_group_urn:
                return HttpResponseRedirect(
                    f"{settings.FRONTEND_URL}?linkedin=error&message=campaign_group_failed"
                )

        # ✅ FIX: ensure account_id and campaign_group are saved as proper URNs
        raw_account_id = str(linkedin_details["account_id"]).strip()
        clean_account_id = (
            raw_account_id
            if raw_account_id.startswith("urn:")
            else f"urn:li:sponsoredAccount:{raw_account_id}"
        )

        raw_campaign_group = str(campaign_group_urn).strip()
        clean_campaign_group = (
            raw_campaign_group
            if raw_campaign_group.startswith("urn:")
            else f"urn:li:sponsoredCampaignGroup:{raw_campaign_group}"
        )

        SocialAccount.objects.update_or_create(
            clinic=clinic,
            platform="linkedin",
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                # ✅ FIX: save as proper URN format
                "account_id": clean_account_id,
                "org_urn": linkedin_details["org_urn"],
                "campaign_group": clean_campaign_group,
                "is_active": True,
            },
        )

        request.session[
            "linkedin_access_token"
        ] = access_token

        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}?linkedin=connected"
        )


class LinkedInStatusAPIView(APIView):

    def get(self, request):
        clinic = resolve_request_clinic(request, required=True)

        social_account = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin",
        ).first()

        if not social_account or not social_account.access_token:
            return Response(
                {
                    "connected": False,
                    "expired": False,
                    "expires_at": None,
                }
            )

        expired = False

        if social_account.expires_at:
            expired = (
                social_account.expires_at < timezone.now()
            )

        return Response(
            {
                "connected": social_account.is_active,
                "expired": expired,
                "expires_at": social_account.expires_at,
                "account_id": social_account.account_id,
                "campaign_group": social_account.campaign_group,
            }
        )


# =====================================================
# OPTIONAL LINKEDIN INSPECTION ENDPOINTS
# =====================================================

class LinkedInAdsAccountsAPIView(APIView):

    def get(self, request):
        clinic = resolve_request_clinic(request, required=True)

        social = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin",
            is_active=True,
        ).first()

        if not social or not social.access_token:
            return Response(
                {"error":"LinkedIn not connected"},
                status=400,
            )

        headers = {
            "Authorization": f"Bearer {social.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202509",
        }

        res = requests.get(
            "https://api.linkedin.com/rest/adAccounts?q=search",
            headers=headers,
        )

        return Response(
            res.json(),
            status=res.status_code,
        )


class LinkedInCampaignAnalyticsAPIView(APIView):

    def get(self, request):
        campaign_urns = request.GET.getlist(
            "campaign_urns"
        )

        if not campaign_urns:
            return Response(
                {
                    "error":"campaign_urns required"
                },
                status=400,
            )

        clinic = resolve_request_clinic(request, required=True)

        social = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin",
            is_active=True,
        ).first()

        if not social:
            return Response(
                {"error":"LinkedIn not connected"},
                status=400,
            )

        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        campaign_list = (
            f"List({','.join(campaign_urns)})"
        )

        url = (
            f"https://api.linkedin.com/rest/adAnalytics"
            f"?q=analytics"
            f"&pivot=CAMPAIGN"
            f"&timeGranularity=DAILY"
            f"&dateRange=(start:(year:{start_date.year},month:{start_date.month},day:{start_date.day}),"
            f"end:(year:{end_date.year},month:{end_date.month},day:{end_date.day}))"
            f"&campaigns={urllib.parse.quote(campaign_list)}"
            f"&fields=impressions,clicks,costInLocalCurrency,likes,shares,comments"
        )

        headers = {
            "Authorization": f"Bearer {social.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202509",
        }

        res = requests.get(
            url,
            headers=headers,
        )

        return Response(
            res.json(),
            status=res.status_code,
        )

class LinkedInCampaignsAPIView(APIView):
    def get(self, request):
        clinic = resolve_request_clinic(request, required=True)

        social = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin",
            is_active=True
        ).first()

        if not social:
            return Response(
                {"error": "LinkedIn not connected"},
                status=400
            )

        headers = {
            "Authorization": f"Bearer {social.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202509",
        }

        res = requests.get(
            "https://api.linkedin.com/rest/adCampaigns?q=search",
            headers=headers
        )

        return Response(
            res.json(),
            status=res.status_code
        )


class LinkedInFullAnalyticsAPIView(APIView):
    def get(self, request):
        return Response({
            "message": (
                "Use "
                "/linkedin/campaign-analytics/"
                " endpoint for analytics"
            )
        })


class GoogleAdsCampaignCallbackAPIView(APIView):
    """
    POST /api/google-ads/callback/
    Zapier callback after campaign creation
    """

    def post(self, request):
        try:
            data = request.data

            campaign_name = data.get("campaign_name")
            google_campaign_id = data.get("campaign_id")
            adgroup_id = data.get("adgroup_id")
            status_val = data.get("status")

            if status_val != "success":
                return Response(
                    {
                        "error": data.get(
                            "message",
                            "Campaign creation failed"
                        )
                    },
                    status=400
                )

            campaign = Campaign.objects.filter(
                campaign_name=campaign_name
            ).order_by("-id").first()

            if not campaign:
                return Response(
                    {
                        "error":
                        f"Campaign '{campaign_name}' not found"
                    },
                    status=404
                )

            platform_data = campaign.platform_data or {}

            existing_google = platform_data.get(
                "google_ads",
                {}
            )

            platform_data["google_ads"] = {
                **existing_google,
                "campaign_resource_name": google_campaign_id,
                "adgroup_id": adgroup_id,
                "status": "created",
            }

            campaign.platform_data = platform_data
            campaign.save(
                update_fields=["platform_data"]
            )

            return Response(
                {
                    "success": True,
                    "campaign_id": str(campaign.id)
                }
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=500
            )


# =====================================================
# FACEBOOK AUTH
# =====================================================

class FacebookLoginAPIView(APIView):
    def get(self, request):
        state = secrets.token_urlsafe(16)
        state_payload = base64.urlsafe_b64encode(
            json.dumps({
                "clinic_id": request.GET.get("clinic_id")
            }).encode()
        ).decode()

        auth_url = (
            "https://www.facebook.com/v19.0/dialog/oauth"
            "?response_type=code"
            f"&client_id={settings.FACEBOOK_CLIENT_ID}"
            f"&redirect_uri={settings.FACEBOOK_REDIRECT_URI}"
            "&scope=public_profile,pages_show_list,pages_read_engagement,ads_management,ads_read,business_management,instagram_basic"
            f"&state={state_payload}"
            "&auth_type=rerequest"
        )

        return redirect(auth_url)


class FacebookCallbackAPIView(APIView):
    def get(self, request):
        try:
            code = request.GET.get("code")

            response = requests.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "client_id": settings.FACEBOOK_CLIENT_ID,
                    "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                    "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
                    "code": code,
                },
            )

            data = response.json()

            if "access_token" not in data:
                return Response(data)

            user_token = data[
                "access_token"
            ]

            long_token = requests.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FACEBOOK_CLIENT_ID,
                    "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                    "fb_exchange_token": user_token,
                },
            ).json()

            user_token = long_token.get("access_token", user_token)

            # NEW — fetch ad accounts
            ad_accounts = requests.get(
                "https://graph.facebook.com/v19.0/me/adaccounts",
                params={"access_token": user_token},
            ).json()

            ad_account_id = None
            if not ad_accounts.get("data"):
                return Response({"error": "No ad accounts found"}, status=400)

            ad_account_id = next(
                (acc["id"] for acc in ad_accounts["data"] if acc.get("account_status") == 1),
                ad_accounts["data"][0]["id"]
            )

            pages = requests.get(
                "https://graph.facebook.com/v19.0/me/accounts",
                params={
                    "access_token": user_token
                },
            ).json()

            if not pages.get("data"):
                return Response(
                    {"error":"No pages found"}
                )

            page = pages["data"][0]

            # NEW — fetch Instagram Business Account
            ig_data = requests.get(
                f"https://graph.facebook.com/v19.0/{page['id']}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": user_token,
                },
            ).json()

            instagram_id = None
            if ig_data.get("instagram_business_account"):
                instagram_id = ig_data["instagram_business_account"]["id"]

            state_raw = request.GET.get("state")

            clinic_id = None
            if state_raw:
                try:
                    state_data = json.loads(
                        base64.urlsafe_b64decode(state_raw).decode()
                    )
                    clinic_id = state_data.get("clinic_id")
                except Exception:
                    pass

            if not clinic_id:
                return Response({"error": "missing clinic_id"}, status=400)

            clinic = Clinic.objects.filter(id=clinic_id).first()

            if not clinic:
                return Response({"error": "invalid clinic"}, status=400)

            SocialAccount.objects.update_or_create(
                clinic=clinic,
                platform="facebook",
                defaults={
                    "access_token": page["access_token"],
                    "user_token": user_token,
                    "page_id": page["id"],
                    "page_name": page["name"],
                    "account_id": ad_account_id,
                    "org_urn": instagram_id,
                    "is_active": True,
                },
            )

            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?facebook=connected&page={page['name']}"
            )

        except Exception as e:
            traceback.print_exc()
            return Response(
                {"error":str(e)}
            )


class FacebookStatusAPIView(APIView):
    def get(self, request):
        clinic = resolve_request_clinic(request, required=True)

        connected = SocialAccount.objects.filter(
            clinic=clinic,
            platform="facebook",
            is_active=True,
        ).exists()

        return Response(
            {
                "connected": connected
            }
        )


class FacebookDisconnectAPIView(APIView):
    def post(self, request):
        clinic = resolve_request_clinic(request, required=True)

        SocialAccount.objects.filter(
            clinic=clinic,
            platform="facebook",
            is_active=True,
        ).update(is_active=False)

        return Response(
            {
                "success":True,
                "message":"Facebook disconnected"
            }
        )


# =====================================================
# GOOGLE AUTH (KEEP MAIN VERSION)
# =====================================================

class GoogleLoginAPIView(APIView):
    def get(self, request):
        customer_id = request.GET.get(
            "customer_id",
            "",
        )

        state_payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "customer_id": customer_id,
                        "clinic_id": request.GET.get("clinic_id")
                    }
                ).encode()
            ).decode()
        )

        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            "?response_type=code"
            f"&client_id={settings.GOOGLE_CLIENT_ID}"
            f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
            "&scope=openid%20email%20profile"
            "%20https://www.googleapis.com/auth/calendar"
            "%20https://www.googleapis.com/auth/adwords"
            "&access_type=offline"
            "&prompt=consent"
            f"&state={state_payload}"
        )

        return redirect(auth_url)


class GoogleCallbackAPIView(APIView):
    def get(self, request):
        try:
            code = request.GET.get("code")
            state_raw = request.GET.get(
                "state",
                "",
            )

            customer_id = ""

            if state_raw:
                try:
                    state_data = json.loads(
                        base64.urlsafe_b64decode(
                            state_raw.encode()
                        ).decode()
                    )
                    customer_id = state_data.get(
                        "customer_id",
                        "",
                    )
                except Exception:
                    pass

            token_response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )

            token_data = token_response.json()

            access_token = token_data.get(
                "access_token"
            )
            refresh_token = token_data.get(
                "refresh_token"
            )

            user_info = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={
                    "Authorization": (
                        f"Bearer {access_token}"
                    )
                },
            ).json()

            email = user_info.get("email")

            state_raw = request.GET.get("state", "")

            state_data = {}
            if state_raw:
                try:
                    state_data = json.loads(
                        base64.urlsafe_b64decode(state_raw.encode()).decode()
                    )
                except Exception:
                    pass

            customer_id = state_data.get("customer_id", "")
            clinic_id = state_data.get("clinic_id")

            if not clinic_id:
                return Response({"error": "missing clinic_id"}, status=400)

            clinic = Clinic.objects.filter(id=clinic_id).first()

            if not clinic:
                return Response({"error": "invalid clinic"}, status=400)

            SocialAccount.objects.update_or_create(
                clinic=clinic,
                platform="google",
                defaults={
                    "access_token": access_token,
                    "user_token": refresh_token,
                    "page_name": email,
                    "customer_id": customer_id,
                    "is_active": True,
                },
            )

            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?google=connected"
            )

        except Exception as e:
            traceback.print_exc()
            return Response(
                {"error":str(e)}
            )


# =====================================================
# SOCIAL ACCOUNTS LIST
# =====================================================

class SocialAccountListAPIView(APIView):
    def get(self, request, clinic_id):
        clinic = resolve_request_clinic(
            request,
            required=True,
        )

        if int(clinic_id) != clinic.id:
            raise ValidationError({"clinic_id": "Clinic access denied"})

        accounts = SocialAccount.objects.filter(
            clinic_id=clinic_id, is_active=True
        ).values("platform", "page_name", "page_id", "customer_id")

        return Response(list(accounts))


# =====================================================
# GOOGLE ADS — CALLBACK (called by Zapier after campaign created)
# =====================================================
class GoogleAdsCampaignCallbackAPIView(APIView):
    """
    POST /api/google-ads/callback/
    Zapier calls this after creating the campaign with the campaign resource name
    """
    def post(self, request):
        try:
            data = request.data
            print("GOOGLE ADS CALLBACK FROM ZAPIER:", data)

            campaign_name      = data.get("campaign_name")
            google_campaign_id = data.get("campaign_id")
            adgroup_id         = data.get("adgroup_id")
            status_val         = data.get("status")

            if status_val != "success":
                return Response(
                    {"error": data.get("message", "Campaign creation failed")},
                    status=status.HTTP_400_BAD_REQUEST
                )

            campaign = Campaign.objects.filter(
                campaign_name=campaign_name
            ).order_by("-id").first()

            if not campaign:
                return Response(
                    {"error": f"Campaign '{campaign_name}' not found in DB"},
                    status=status.HTTP_404_NOT_FOUND
                )

            platform_data = campaign.platform_data or {}
            existing_google = platform_data.get("google_ads", {})
            if not isinstance(existing_google, dict):
                existing_google = {}

            platform_data["google_ads"] = {
                **existing_google,
                "campaign_resource_name": google_campaign_id,
                "adgroup_id":             adgroup_id,
                "status":                 "created",
            }
            campaign.platform_data = platform_data
            campaign.save(update_fields=["platform_data"])

            logger.info(
                "[GoogleAdsCallback] Campaign '%s' updated with campaign_id: %s",
                campaign_name, google_campaign_id
            )

            return Response(
                {"success": True, "campaign_id": str(campaign.id)},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error("[GoogleAdsCallback] Error: %s", str(e))
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =====================================================
# GOOGLE ADS — INSIGHTS
# =====================================================
class GoogleAdsInsightsAPIView(APIView):
    """
    GET /api/google-ads/insights/?clinic_id=1
    Fetches campaign performance insights from Google Ads API
    """
    def get(self, request):
        try:
            clinic_id = request.query_params.get("clinic_id")
            if not clinic_id:
                return Response(
                    {"error": "clinic_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            google_account = SocialAccount.objects.filter(
                clinic_id=clinic_id,
                platform="google",
                is_active=True
            ).first()

            if not google_account:
                return Response(
                    {"error": "Google Ads not connected for this clinic"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            refresh_token = google_account.user_token
            customer_id   = google_account.customer_id or getattr(
                settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""
            )

            if not refresh_token:
                return Response(
                    {"error": "Google refresh token missing. Please reconnect."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            auth_res = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id":     settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type":    "refresh_token",
                }
            )
            auth_json = auth_res.json()

            if "access_token" not in auth_json:
                return Response(
                    {"error": "Failed to refresh Google token", "details": auth_json},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            access_token = auth_json["access_token"]
            cust_id      = str(customer_id).replace("-", "")

            headers = {
                "Authorization":   f"Bearer {access_token}",
                "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "Content-Type":    "application/json",
            }

            login_id = str(
                getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
            ).replace("-", "")
            if login_id and login_id != cust_id:
                headers["login-customer-id"] = login_id

            query = """
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.ctr,
                    metrics.average_cpc,
                    metrics.cost_micros,
                    metrics.conversions
                FROM campaign
                WHERE campaign.status != 'REMOVED'
                ORDER BY campaign.id DESC
                LIMIT 200
            """

            insights_res = requests.post(
                f"https://googleads.googleapis.com/v20/customers/{cust_id}/googleAds:search",
                headers=headers,
                json={"query": query}
            )
            insights_data = insights_res.json()

            if "error" in insights_data:
                return Response(
                    {"error": "Google Ads API error", "details": insights_data},
                    status=status.HTTP_502_BAD_GATEWAY
                )

            campaigns = []
            for row in insights_data.get("results", []):
                camp    = row.get("campaign", {})
                metrics = row.get("metrics", {})
                campaigns.append({
                    "campaign_id":   camp.get("id"),
                    "campaign_name": camp.get("name"),
                    "status":        camp.get("status"),
                    "type":          camp.get("advertisingChannelType"),
                    "impressions":   int(metrics.get("impressions", 0)),
                    "clicks":        int(metrics.get("clicks", 0)),
                    "ctr":           round(float(metrics.get("ctr", 0)) * 100, 2),
                    "avg_cpc":       round(int(metrics.get("averageCpc", 0)) / 1_000_000, 2),
                    "cost":          round(int(metrics.get("costMicros", 0)) / 1_000_000, 2),
                    "conversions":   float(metrics.get("conversions", 0)),
                })

            return Response({
                "success":   True,
                "clinic_id": clinic_id,
                "total":     len(campaigns),
                "campaigns": campaigns,
            })

        except Exception as e:
            logger.error("[GoogleAdsInsights] Error: %s", traceback.format_exc())
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
