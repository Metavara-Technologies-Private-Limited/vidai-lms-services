
# =====================================================
# restapi/views/social_auth_views.py
# =====================================================

import json
import base64
import secrets
import traceback
import urllib.parse
from datetime import datetime, timedelta

import requests

from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from django.utils import timezone
from restapi.models import Clinic, Campaign

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from restapi.models import Clinic, Campaign
from restapi.models.social_account import SocialAccount
from restapi.utils.linkedin import (
    create_campaign_group,
    fetch_linkedin_account_details,
)
from restapi.utils.clinic_scope import resolve_request_clinic


# =====================================================
# LINKEDIN AUTH
# =====================================================

class LinkedInLoginAPIView(APIView):
    def get(self, request):
        clinic_id = request.GET.get("clinic_id")

        if clinic_id:
            request.session["linkedin_clinic_id"] = clinic_id

        scopes = [
            "openid",
            "profile",
            "email",
            "r_ads",
            "r_ads_reporting",
            "rw_ads",
            "r_organization_social",
        ]

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

        clinic_id = request.session.get(
            "linkedin_clinic_id"
        )

        clinic = (
            Clinic.objects.filter(id=clinic_id).first()
            if clinic_id
            else Clinic.objects.first()
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

        SocialAccount.objects.update_or_create(
            clinic=clinic,
            platform="linkedin",
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "account_id": linkedin_details[
                    "account_id"
                ],
                "org_urn": linkedin_details[
                    "org_urn"
                ],
                "campaign_group": campaign_group_urn,
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
        clinic = Clinic.objects.first()

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
        clinic = Clinic.objects.first()

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

        clinic = Clinic.objects.first()

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
        clinic = Clinic.objects.first()

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
        request.session[
            "facebook_state"
        ] = state

        auth_url = (
            "https://www.facebook.com/v19.0/dialog/oauth"
            "?response_type=code"
            f"&client_id={settings.FACEBOOK_CLIENT_ID}"
            f"&redirect_uri={settings.FACEBOOK_REDIRECT_URI}"
            "&scope=public_profile,email,pages_show_list,pages_read_engagement,pages_manage_posts,read_insights"
            f"&state={state}"
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

            clinic = Clinic.objects.first()

            SocialAccount.objects.update_or_create(
                clinic=clinic,
                platform="facebook",
                defaults={
                    "access_token": page[
                        "access_token"
                    ],
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
            return Response(
                {"error":str(e)}
            )


class FacebookStatusAPIView(APIView):
    def get(self, request):
        clinic = Clinic.objects.first()

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
        clinic = Clinic.objects.first()

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
                        "customer_id": customer_id
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
            raise ValidationError(
                {
                    "clinic_id": (
                        "Clinic access denied"
                    )
                }
            )

        accounts = SocialAccount.objects.filter(
            clinic_id=clinic_id,
            is_active=True,
        ).values(
            "platform",
            "page_name",
            "page_id",
            "customer_id",
        )

        return Response(
            list(accounts)
        )
