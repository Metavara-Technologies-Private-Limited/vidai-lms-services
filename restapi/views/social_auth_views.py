# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import json
import base64
import logging
import requests
import secrets
import traceback
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
import urllib.parse

from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from restapi.models import Clinic, Campaign
from restapi.models.social_account import SocialAccount


# =====================================================
# SOCIAL AUTH - LINKEDIN
# =====================================================

class LinkedInLoginAPIView(APIView):
    def get(self, request):
        # Get clinic ID from query params if needed
        clinic_id = request.GET.get('clinic_id')
        
        # Store clinic_id in session to use in callback
        if clinic_id:
            request.session['linkedin_clinic_id'] = clinic_id
        
        # Define scopes as a list and join properly
        scopes = [
            "openid",
            "profile", 
            "email",
            "r_ads",
            "r_ads_reporting",
            "rw_ads",
            "r_organization_social"
        ]
        
        # Join with %20 for URL encoding
        scope_param = "%20".join(scopes)
        
        auth_url = (
            "https://www.linkedin.com/oauth/v2/authorization"
            "?response_type=code"
            f"&client_id={settings.LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
            f"&scope={scope_param}"
            "&prompt=login"
        )
        return redirect(auth_url)


class LinkedInCallbackAPIView(APIView):
    def get(self, request):
        code = request.GET.get("code")
        error = request.GET.get("error")

        print("=" * 60)
        print("LINKEDIN CALLBACK RECEIVED")
        print(f"Code: {code[:50] if code else 'None'}...")
        print(f"Error: {error}")
        print("=" * 60)

        # --------------------------------------------------
        # HANDLE ERROR FROM LINKEDIN
        # --------------------------------------------------
        if error:
            print(f"LinkedIn OAuth error: {error}")
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&error={error}"
            )

        # --------------------------------------------------
        # EXCHANGE CODE FOR ACCESS TOKEN
        # --------------------------------------------------
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }

        print("Exchanging code for token...")

        response = requests.post(token_url, data=data)
        token_data = response.json()

        access_token = token_data.get("access_token")
        if access_token:
            clinic = Clinic.objects.first()

            SocialAccount.objects.update_or_create(
                clinic=clinic,
                platform="linkedin",
                defaults={
                    "access_token": access_token,
                    "is_active": True,
                },
            )
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}?linkedin=connected")


class LinkedInStatusAPIView(APIView):
    """
    Returns LinkedIn connection + expiry status
    """

    def get(self, request):
        clinic = Clinic.objects.first()

        social_account = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin"
        ).first()

        # ------------------------------------------
        # NOT CONNECTED
        # ------------------------------------------
        if not social_account or not social_account.access_token:
            return Response({
                "connected": False,
                "expired": False,
                "expires_at": None
            })

        # ------------------------------------------
        # CHECK EXPIRY
        # ------------------------------------------
        expired = False

        if social_account.expires_at:
            expired = social_account.expires_at < timezone.now()

        # ------------------------------------------
        # RESPONSE
        # ------------------------------------------
        return Response({
            "connected": social_account.is_active,
            "expired": expired,
            "expires_at": social_account.expires_at
        })

# class LinkedInStatusAPIView(APIView):
#     def get(self, request):
#         return Response({"connected": bool(request.session.get("linkedin_token"))})




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
            response = requests.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params=params
            )
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
        connected = SocialAccount.objects.filter(
            clinic=clinic, platform="facebook", is_active=True
        ).exists()
        return Response({"connected": connected})


class FacebookDisconnectAPIView(APIView):
    def post(self, request):
        try:
            clinic = Clinic.objects.first()
            SocialAccount.objects.filter(
                clinic=clinic,
                platform="facebook",
                is_active=True
            ).update(is_active=False)
            return Response({"success": True, "message": "Facebook disconnected"})
        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


# =====================================================
# SOCIAL AUTH - GOOGLE
# =====================================================
class GoogleLoginAPIView(APIView):
    def get(self, request):
        customer_id = request.GET.get("customer_id", "")

        state_payload = base64.urlsafe_b64encode(
            json.dumps({"customer_id": customer_id}).encode()
        ).decode()

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

            state_raw = request.GET.get("state", "")
            customer_id = ""
            if state_raw:
                try:
                    state_data = json.loads(
                        base64.urlsafe_b64decode(state_raw.encode()).decode()
                    )
                    customer_id = state_data.get("customer_id", "")
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

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")

            user_info = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            ).json()

            email = user_info.get("email")
            clinic = Clinic.objects.first()

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

            return HttpResponseRedirect(f"{settings.FRONTEND_URL}?google=connected")

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)})


# =====================================================
# SOCIAL ACCOUNTS LIST
# =====================================================
class SocialAccountListAPIView(APIView):
    def get(self, request, clinic_id):
        clinic = resolve_request_clinic(request, required=True)
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

            # -------------------------------------------------------
            # FIXED QUERY:
            # - Removed LAST_30_DAYS filter so newly created campaigns appear
            # - Removed REMOVED campaigns
            # - Order by campaign.id DESC so newest appear first
            # - Increased LIMIT to 200
            # -------------------------------------------------------
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