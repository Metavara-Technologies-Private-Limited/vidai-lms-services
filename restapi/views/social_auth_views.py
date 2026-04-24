# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
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

from restapi.models import Clinic
from restapi.models.social_account import SocialAccount
from restapi.utils.linkedin import create_campaign_group, fetch_linkedin_account_details



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
        refresh_token = token_data.get("refresh_token")  # may be None
        expires_in = token_data.get("expires_in")        # seconds

        print(f"Token exchange status: {response.status_code}")
        print(f"Has access_token: {bool(access_token)}")

        if not access_token:
            print(f"❌ Failed to get access token: {token_data}")
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=token_exchange_failed"
            )

        # --------------------------------------------------
        # CALCULATE EXPIRY TIME
        # --------------------------------------------------
        expires_at = None
        if expires_in:
            expires_at = timezone.now() + timedelta(seconds=expires_in)

        print(f"Expires at: {expires_at}")
        print(f"Has refresh token: {bool(refresh_token)}")
        
  
        
        
        # --------------------------------------------------
        # FETCH ACCOUNT DETAILS
        # --------------------------------------------------
        linkedin_details = fetch_linkedin_account_details(access_token)

        if not linkedin_details:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=no_ad_account"
            )

        print("LinkedIn details:", linkedin_details)

        # --------------------------------------------------
        # GET CLINIC
        # --------------------------------------------------
        clinic_id = request.session.get("linkedin_clinic_id")
        clinic = Clinic.objects.filter(id=clinic_id).first() if clinic_id else Clinic.objects.first()

        if not clinic:
            return HttpResponseRedirect(
                f"{settings.FRONTEND_URL}?linkedin=error&message=no_clinic"
            )

        # --------------------------------------------------
        # CHECK EXISTING ACCOUNT (IMPORTANT)
        # --------------------------------------------------
        existing_account = SocialAccount.objects.filter(
            clinic=clinic,
            platform="linkedin"
        ).first()

        campaign_group_urn = None

        if existing_account and existing_account.campaign_group:
            campaign_group_urn = existing_account.campaign_group
            print("✅ Reusing existing campaign group:", campaign_group_urn)
        else:
            print("⚙️ Creating new campaign group...")
            campaign_group_urn = create_campaign_group(
                access_token,
                linkedin_details["account_id"]
            )

            if not campaign_group_urn:
                return HttpResponseRedirect(
                    f"{settings.FRONTEND_URL}?linkedin=error&message=campaign_group_failed"
                )

            print("✅ Created campaign group:", campaign_group_urn)

        # --------------------------------------------------
        # SAVE TO DB
        # --------------------------------------------------
        social_account, created = SocialAccount.objects.update_or_create(
            clinic=clinic,
            platform="linkedin",
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "account_id": linkedin_details["account_id"],
                "org_urn": linkedin_details["org_urn"],
                "campaign_group": campaign_group_urn,
                "default_geo_urn":"urn:li:geo:102713980",
                "default_bid_strategy":"MAX_DELIVERY",
                "default_objective":"LEAD_GENERATION",
                "is_active": True,
            },
        )

        print(f"SocialAccount {'created' if created else 'updated'}")
        print(f"Token saved: {access_token[:50]}...")

        # --------------------------------------------------
        # STORE IN SESSION (OPTIONAL)
        # --------------------------------------------------
        request.session["linkedin_access_token"] = access_token

        # --------------------------------------------------
        # REDIRECT BACK TO FRONTEND
        # --------------------------------------------------
        print("Redirecting to frontend...")

        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}?linkedin=connected"
        )


class LinkedInAdsAccountsAPIView(APIView):
    """Get all ad accounts for the authenticated LinkedIn user"""
    
    def get(self, request):
        clinic = Clinic.objects.first()
        social_account = SocialAccount.objects.filter(
            clinic=clinic, 
            platform="linkedin", 
            is_active=True
        ).first()
        
        if not social_account or not social_account.access_token:
            return Response({"error": "LinkedIn not connected"}, status=400)
        
        headers = {
            'Authorization': f'Bearer {social_account.access_token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202509'  # ⬅️ ADD THIS LINE
        }
        
        # Get ad accounts
        url = "https://api.linkedin.com/rest/adAccounts?q=search"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return Response({"error": "Failed to fetch ad accounts", "details": response.text}, status=response.status_code)
        
        return Response(response.json())


class LinkedInCampaignsAPIView(APIView):
    """Get all campaigns for a specific ad account"""
    
    def get(self, request):
        account_urn = request.GET.get('account_urn')
        if not account_urn:
            return Response({"error": "account_urn parameter required"}, status=400)
        
        clinic = Clinic.objects.first()
        social_account = SocialAccount.objects.filter(
            clinic=clinic, 
            platform="linkedin", 
            is_active=True
        ).first()
        
        if not social_account or not social_account.access_token:
            return Response({"error": "LinkedIn not connected"}, status=400)
        
        headers = {
            'Authorization': f'Bearer {social_account.access_token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202509'  # ⬅️ ADD THIS LINE
        }
        
        url = f"https://api.linkedin.com/rest/campaigns?q=search&account={account_urn}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return Response({"error": "Failed to fetch campaigns", "details": response.text}, status=response.status_code)
        
        return Response(response.json())


class LinkedInCampaignAnalyticsAPIView(APIView):
    """Get analytics for campaigns (impressions, clicks, cost, etc.)"""
    
    def get(self, request):
        campaign_urns = request.GET.getlist('campaign_urns')
        if not campaign_urns:
            return Response({"error": "campaign_urns parameter required"}, status=400)
        
        # Date range (default: last 30 days)
        end_date = datetime.now()
        start_date = request.GET.get('start_date')
        end_date_param = request.GET.get('end_date')
        
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start = end_date - timedelta(days=30)
        
        if end_date_param:
            end = datetime.strptime(end_date_param, '%Y-%m-%d')
        else:
            end = end_date
        
        clinic = Clinic.objects.first()
        social_account = SocialAccount.objects.filter(
            clinic=clinic, 
            platform="linkedin", 
            is_active=True
        ).first()
        
        if not social_account or not social_account.access_token:
            return Response({"error": "LinkedIn not connected"}, status=400)
        
        headers = {
            'Authorization': f'Bearer {social_account.access_token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202509'  # ⬅️ ADD THIS LINE
        }
        
        # Build campaign list
        campaign_list = f"List({','.join(campaign_urns)})"
        
        # Build URL with all parameters
        url = (
            f"https://api.linkedin.com/rest/adAnalytics"
            f"?q=analytics"
            f"&pivot=CAMPAIGN"
            f"&timeGranularity=DAILY"
            f"&dateRange=(start:(year:{start.year},month:{start.month},day:{start.day}),"
            f"end:(year:{end.year},month:{end.month},day:{end.day}))"
            f"&campaigns={urllib.parse.quote(campaign_list)}"
            f"&fields=impressions,clicks,costInLocalCurrency,landingPageClicks,"
            f"externalWebsiteConversions,likes,shares,comments,dateRange,pivotValues"
        )
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return Response({"error": "Failed to fetch analytics", "details": response.text}, status=response.status_code)
        
        return Response(response.json())


class LinkedInFullAnalyticsAPIView(APIView):
    """Get complete analytics: accounts -> campaigns -> analytics in one request"""
    
    def get(self, request):
        clinic = Clinic.objects.first()
        social_account = SocialAccount.objects.filter(
            clinic=clinic, 
            platform="linkedin", 
            is_active=True
        ).first()
        
        if not social_account or not social_account.access_token:
            return Response({"error": "LinkedIn not connected"}, status=400)
        
        headers = {
            'Authorization': f'Bearer {social_account.access_token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202509'  # ⬅️ ADD THIS LINE
        }
        
        result = {
            "ad_accounts": [],
            "campaigns": {},
            "analytics": {}
        }
        
        # 1. Get all ad accounts
        accounts_url = "https://api.linkedin.com/rest/adAccounts?q=search"
        accounts_response = requests.get(accounts_url, headers=headers)
        
        if accounts_response.status_code != 200:
            return Response({"error": "Failed to fetch ad accounts", "details": accounts_response.text}, status=accounts_response.status_code)
        
        accounts_data = accounts_response.json()
        result["ad_accounts"] = accounts_data.get("elements", [])
        
        # 2. For each account, get campaigns
        for account in result["ad_accounts"]:
            account_urn = account.get("id")
            if not account_urn:
                continue
            
            campaigns_url = f"https://api.linkedin.com/rest/campaigns?q=search&account={account_urn}"
            campaigns_response = requests.get(campaigns_url, headers=headers)
            
            if campaigns_response.status_code == 200:
                campaigns_data = campaigns_response.json()
                result["campaigns"][account_urn] = campaigns_data.get("elements", [])
                
                # 3. Get analytics for campaigns
                campaign_urns = [c.get("id") for c in result["campaigns"][account_urn] if c.get("id")]
                if campaign_urns:
                    # Last 30 days
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    campaign_list = f"List({','.join(campaign_urns)})"
                    
                    analytics_url = (
                        f"https://api.linkedin.com/rest/adAnalytics"
                        f"?q=analytics"
                        f"&pivot=CAMPAIGN"
                        f"&timeGranularity=DAILY"
                        f"&dateRange=(start:(year:{start_date.year},month:{start_date.month},day:{start_date.day}),"
                        f"end:(year:{end_date.year},month:{end_date.month},day:{end_date.day}))"
                        f"&campaigns={urllib.parse.quote(campaign_list)}"
                        f"&fields=impressions,clicks,costInLocalCurrency,landingPageClicks,dateRange"
                    )
                    
                    analytics_response = requests.get(analytics_url, headers=headers)
                    if analytics_response.status_code == 200:
                        result["analytics"][account_urn] = analytics_response.json().get("elements", [])
        
        return Response(result)



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
