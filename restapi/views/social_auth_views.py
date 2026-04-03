# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import requests
import secrets
import traceback

from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from rest_framework.views import APIView
from rest_framework.response import Response

from restapi.models import Clinic
from restapi.models.social_account import SocialAccount


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
    def get(self, request):
        return Response({"connected": bool(request.session.get("linkedin_token"))})


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


class GoogleLoginAPIView(APIView):
    def get(self, request):
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            "?response_type=code"
            f"&client_id={settings.GOOGLE_CLIENT_ID}"
            f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
            "&scope=openid email profile https://www.googleapis.com/auth/calendar"
            "&access_type=offline"
            "&prompt=consent"
        )
        return redirect(auth_url)


class GoogleCallbackAPIView(APIView):
    def get(self, request):
        try:
            code = request.GET.get("code")

            # Step 1: Exchange code for token
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

            # Step 2: Get user info
            user_info = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            ).json()

            email = user_info.get("email")

            # Step 3: Save in DB
            clinic = Clinic.objects.first()

            SocialAccount.objects.update_or_create(
                clinic=clinic,
                platform="google",
                defaults={
                    "access_token": access_token,
                    "user_token": refresh_token,
                    "page_name": email,
                    "is_active": True,
                },
            )

            return HttpResponseRedirect(f"{settings.FRONTEND_URL}?google=connected")

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)})
