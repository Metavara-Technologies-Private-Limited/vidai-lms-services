# # =====================================================
# # Imports (ONLY REQUIRED)
# # =====================================================
# import logging
# import traceback
# import requests

# from django.db import transaction
# from django.utils import timezone
# from django.utils.html import strip_tags
# from django.conf import settings

# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status

# from drf_yasg.utils import swagger_auto_schema

# from restapi.models import Campaign, CampaignSocialMediaConfig
# from restapi.models.social_account import SocialAccount
# from restapi.services.campaign_social_post_service import _is_direct_image_url
# from restapi.serializers.campaign_serializer import SocialMediaCampaignSerializer

# from restapi.services.campaign_social_post_service import (
#     post_to_facebook,
#     post_to_instagram,
#     post_to_linkedin,
# )
# from restapi.services.google_ads_service import create_google_ads_campaign
# from restapi.services.zapier_service import send_to_zapier_social

# logger = logging.getLogger(__name__)


# # -------------------------------------------------------------------
# # Social Media Campaign Create API View (POST)
# # -------------------------------------------------------------------
# class SocialMediaCampaignCreateAPIView(APIView):

#     @swagger_auto_schema(
#         operation_description="Create Social Media Campaign Only",
#         request_body=SocialMediaCampaignSerializer,
#         responses={
#             201: "Campaign Created Successfully",
#             400: "Validation Error",
#             500: "Internal Server Error",
#         },
#         tags=["Social Media Campaign"],
#     )
#     @transaction.atomic
#     def post(self, request):
#         try:
#             print("SOCIAL DATA:", request.data)
#             serializer = SocialMediaCampaignSerializer(data=request.data)
#             serializer.is_valid(raise_exception=True)

#             data = serializer.validated_data

#             mode_mapping = {
#                 "organic_posting": Campaign.ORGANIC,
#                 "paid_advertising": Campaign.PAID,
#             }

#             created_campaigns = []

#             for mode in data["campaign_mode"]:

#                 raw_platform_data = data.get("platform_data") or {}
#                 raw_campaign_content = (data.get("campaign_content") or "").strip()

#                 # Helper: extract first image URL from mixed text+URL string
#                 def _extract_image_url(text):
#                     if not text:
#                         return None, text
#                     text = text.strip()
#                     # Case 1: entire string is just a URL
#                     if (
#                         _is_direct_image_url(text)
#                         and "\n" not in text
#                         and " " not in text
#                     ):
#                         return text, ""
#                     # Case 2: URL embedded inside text
#                     tokens = text.replace("\n", " ").split()
#                     for token in tokens:
#                         token = token.strip(".,;!?\"'")
#                         if _is_direct_image_url(token):
#                             clean = text.replace(token, "").strip().strip(".,;!?\n ")
#                             return token, clean
#                     return None, text

#                 # Resolve facebook message text
#                 _platform_facebook = strip_tags(
#                     raw_platform_data.get("facebook", "") or ""
#                 ).strip()
#                 _campaign_content = strip_tags(raw_campaign_content).strip()

#                 # Extract any embedded image URL from the text fields
#                 _fb_extracted_url, _platform_facebook = _extract_image_url(
#                     _platform_facebook
#                 )
#                 _cc_extracted_url, _campaign_content = _extract_image_url(
#                     _campaign_content
#                 )

#                 facebook_message = _platform_facebook or _campaign_content

#                 # Resolve image_url
#                 # Priority: 1. Explicit image_url field  2. platform_data.facebook  3. campaign_content
#                 _raw_image_url = (request.data.get("image_url") or "").strip()
#                 if _raw_image_url:
#                     _extracted, _ = _extract_image_url(_raw_image_url)
#                     image_url_field = _extracted or None
#                     if image_url_field != _raw_image_url:
#                         print(
#                             f"image_url cleaned: {repr(_raw_image_url[:80])} -> {image_url_field}"
#                         )
#                 else:
#                     image_url_field = None

#                 if not image_url_field and _fb_extracted_url:
#                     image_url_field = _fb_extracted_url
#                     print(
#                         f"image_url extracted from platform_data.facebook: {image_url_field}"
#                     )

#                 if not image_url_field and _cc_extracted_url:
#                     image_url_field = _cc_extracted_url
#                     print(
#                         f"image_url extracted from campaign_content: {image_url_field}"
#                     )

#                 print("=" * 60)
#                 print("DEBUG raw platform_data   :", raw_platform_data)
#                 print("DEBUG campaign_content     :", _campaign_content)
#                 print("DEBUG facebook_message     :", facebook_message)
#                 print("DEBUG image_url            :", image_url_field)
#                 print("=" * 60)

#                 # Build selected_start / selected_end
#                 from datetime import datetime, time, date as date_type

#                 start = data["start_date"]
#                 end = data["end_date"]

#                 selected_start = timezone.make_aware(
#                     datetime.combine(
#                         (
#                             start
#                             if isinstance(start, date_type)
#                             else datetime.strptime(start, "%Y-%m-%d").date()
#                         ),
#                         time(0, 0, 0),
#                     )
#                 )
#                 selected_end = timezone.make_aware(
#                     datetime.combine(
#                         (
#                             end
#                             if isinstance(end, date_type)
#                             else datetime.strptime(end, "%Y-%m-%d").date()
#                         ),
#                         time(23, 59, 59),
#                     )
#                 )

#                 # =====================================================
#                 # FIX: Only store budget for SELECTED platforms
#                 # Previously: budget_data=data.get("budget_data") or {}
#                 # stored ALL platforms (instagram/facebook/linkedin)
#                 # even when only 2 were selected — causing wrong totals.
#                 # Now we filter to only the selected platforms + recompute total.
#                 # =====================================================
#                 selected_platforms = data["select_ad_accounts"]
#                 raw_budget_data = data.get("budget_data") or {}
#                 filtered_budget = {
#                     p: raw_budget_data.get(p, 0) for p in selected_platforms
#                 }
#                 filtered_budget["total"] = sum(
#                     v for k, v in filtered_budget.items() if k != "total"
#                 )

#                 campaign = Campaign.objects.create(
#                     clinic_id=data["clinic"],
#                     campaign_name=data["campaign_name"],
#                     campaign_description=data["campaign_description"],
#                     campaign_objective=data["campaign_objective"],
#                     target_audience=data["target_audience"],
#                     start_date=data["start_date"],
#                     end_date=data["end_date"],
#                     campaign_mode=mode_mapping.get(mode),
#                     campaign_content=facebook_message,
#                     selected_start=selected_start,
#                     selected_end=selected_end,
#                     enter_time=data["enter_time"],
#                     platform_data=raw_platform_data,
#                     budget_data=filtered_budget,
#                     image_url=image_url_field,
#                     is_active=True,
#                 )

#                 print("=" * 60)
#                 print("PLATFORM DATA:", campaign.platform_data)
#                 print("FACEBOOK MESSAGE:", facebook_message)
#                 print("IMAGE URL SAVED:", campaign.image_url)
#                 print("=" * 60)

#                 channels = []

#                 for platform in data["select_ad_accounts"]:
#                     CampaignSocialMediaConfig.objects.create(
#                         campaign=campaign,
#                         platform_name=platform,
#                         is_active=True,
#                     )
#                     channels.append(platform)

#                 clinic_id = data["clinic"]

#                 # social = SocialAccount.objects.filter(
#                 #     clinic_id=clinic_id,
#                 #     platform="facebook",
#                 #     is_active=True
#                 # ).first()

#                 # fb_post_id = None

#                 # print("=" * 60)
#                 # print("CHANNELS:", channels)
#                 # print("SOCIAL ACCOUNT FOUND:", social)
#                 # print("=" * 60)

#                 # if "facebook" in channels:
#                 #     # if not social:
#                 #     #     print("NO FACEBOOK SOCIAL ACCOUNT for clinic_id:", clinic_id)
#                 #     #     return Response(
#                 #     #         {"error": "Facebook not connected for this clinic"},
#                 #     #         status=400
#                 #     #     )

#                 #     if not facebook_message:
#                 #         facebook_message = campaign.campaign_name

#                 #     formatted_message = (
#                 #         f"📢 {campaign.campaign_name}\n\n"
#                 #         f"{facebook_message}\n\n"
#                 #         f"📅 Campaign Duration: "
#                 #         f"{campaign.start_date.strftime('%d %b %Y')} – "
#                 #         f"{campaign.end_date.strftime('%d %b %Y')}\n"
#                 #         f"⏰ Scheduled Time: "
#                 #         f"{campaign.enter_time.strftime('%I:%M %p') if campaign.enter_time else 'N/A'}\n"
#                 #         f"🎯 Objective: {campaign.campaign_objective}\n"
#                 #         f"👥 Target Audience: {campaign.target_audience}\n\n"
#                 #         f"#LMS #Campaign #{campaign.campaign_name.replace(' ', '')}"
#                 #     )

#                 #     fb_post_id = None

#                 #     print("=" * 60)
#                 #     print("CHANNELS:", channels)
#                 #     print("FORMATTED MESSAGE:", formatted_message[:80], "...")
#                 #     print("=" * 60)

#                 #     if "facebook" in channels:
#                 #         social_fb = SocialAccount.objects.filter(
#                 #             clinic_id=clinic_id, platform="facebook", is_active=True
#                 #         ).first()

#                 #         if not social_fb:
#                 #             print(
#                 #                 "NO FACEBOOK SOCIAL ACCOUNT for clinic_id:", clinic_id
#                 #             )
#                 #             return Response(
#                 #                 {"error": "Facebook not connected for this clinic"},
#                 #                 status=400,
#                 #             )

#                 #         print(">>> CALLING post_to_facebook()")
#                 #         print("Page ID   :", social_fb.page_id)
#                 #         print("Page Name :", social_fb.page_name)
#                 #         print(
#                 #             "Token (20):",
#                 #             (
#                 #                 social_fb.access_token[:20]
#                 #                 if social_fb.access_token
#                 #                 else "NONE"
#                 #             ),
#                 #         )
#                 #         print("Image URL :", campaign.image_url)

#                 #         send_to_zapier_social(
#                 #             {
#                 #                 "event": "social_campaign_created",
#                 #                 "campaign_id": str(campaign.id),
#                 #                 "campaign_name": campaign.campaign_name,
#                 #                 "platforms": channels,
#                 #                 "budget": filtered_budget,
#                 #                 "content": facebook_message,
#                 #                 "image_url": campaign.image_url,
#                 #                 "status": data.get("status"),
#                 #                 "start_date": str(data.get("start_date")),
#                 #                 "end_date": str(data.get("end_date")),
#                 #             }
#                 #         )

#                 #         fb_response = post_to_facebook(
#                 #             page_id=social_fb.page_id,
#                 #             page_token=social_fb.access_token,
#                 #             message=formatted_message,
#                 #             image_url=campaign.image_url,
#                 #         )

#                 #         print("FB POST FULL RESPONSE:", fb_response)
#                 #         # Use post_id (full page_post format) if available, else fall back to id
#                 #         fb_post_id = fb_response.get("post_id") or fb_response.get("id")
#                 #         print("FB POST ID:", fb_post_id)

#                 #         if fb_post_id:
#                 #             campaign.post_id = fb_post_id
#                 #             campaign.save(update_fields=["post_id"])
#                 #             print("FB POST ID SAVED:", fb_post_id)
#                 #         else:
#                 #             print("FB POST ID IS NONE — check FB error above")

#                 #         # =====================================================
#                 #         # CREATE FACEBOOK AD CAMPAIGN (Paid mode only)
#                 #         # =====================================================
#                 #         if "facebook" in channels:
#                 #             try:
#                 #                 fb_budget = filtered_budget.get("facebook", 200)
#                 #                 fb_camp_r = requests.post(
#                 #                     f"https://graph.facebook.com/v19.0/act_{settings.FB_AD_ACCOUNT_ID}/campaigns",
#                 #                     data={
#                 #                         "name": campaign.campaign_name,
#                 #                         "objective": "OUTCOME_LEADS",
#                 #                         "status": "PAUSED",
#                 #                         "daily_budget": int(fb_budget) * 100,
#                 #                         "special_ad_categories": "[]",
#                 #                         "is_adset_budget_sharing_enabled": False,
#                 #                         "access_token": settings.FB_ACCESS_TOKEN,
#                 #                     }
#                 #                 )
#                 #                 fb_camp_data = fb_camp_r.json()
#                 #                 if "id" in fb_camp_data:
#                 #                     campaign.fb_campaign_id = fb_camp_data["id"]
#                 #                     campaign.save(update_fields=["fb_campaign_id"])
#                 #                     print("FB AD CAMPAIGN CREATED:", fb_camp_data["id"])
#                 #                 else:
#                 #                     print("FB AD CAMPAIGN ERROR:", fb_camp_data)
#                 #             except Exception:
#                 #                 print("FB AD CAMPAIGN FAILED:\n" + traceback.format_exc())

#                 #     if "instagram" in channels:
#                 #         if not campaign.image_url:
#                 #             print(
#                 #                 "Skipping Instagram: image_url is required for Instagram posts"
#                 #             )
#                 #         else:
#                 #             social_ig = SocialAccount.objects.filter(
#                 #                 clinic_id=clinic_id, platform="facebook", is_active=True
#                 #             ).first()

#                 #             ig_user_id = getattr(social_ig, "instagram_id", None)

#                 #             if not social_ig or not ig_user_id:
#                 #                 print(
#                 #                     "Instagram not connected or instagram_id missing on SocialAccount"
#                 #                 )
#                 #             else:
#                 #                 print(">>> CALLING post_to_instagram()")
#                 #                 print("IG User ID :", ig_user_id)
#                 #                 ig_response = post_to_instagram(
#                 #                     ig_user_id=ig_user_id,
#                 #                     access_token=social_ig.access_token,
#                 #                     message=formatted_message,
#                 #                     image_url=campaign.image_url,
#                 #                 )
#                 #                 print("IG POST RESPONSE:", ig_response)

#                 #     if "linkedin" in channels:
#                 #         social_li = SocialAccount.objects.filter(
#                 #             clinic_id=clinic_id, platform="linkedin", is_active=True
#                 #         ).first()

#                 #         if not social_li:
#                 #             print("LinkedIn not connected for clinic_id:", clinic_id)
#                 #         else:
#                 #             print(">>> CALLING post_to_linkedin()")
#                 #             print("Author URN :", social_li.linkedin_urn)
#                 #             li_response = post_to_linkedin(
#                 #                 access_token=social_li.linkedin_token,
#                 #                 author_urn=social_li.linkedin_urn,
#                 #                 message=formatted_message,
#                 #                 image_url=campaign.image_url,
#                 #             )
#                 #             print("LI POST RESPONSE:", li_response)

#                 #     # =====================================================
#                 #     # GOOGLE ADS CAMPAIGN (NEW)
#                 #     # =====================================================
#                 #     if "google_ads" in channels:

#                 #         google_account = SocialAccount.objects.filter(
#                 #             clinic_id=clinic_id,
#                 #             platform="google",
#                 #             is_active=True
#                 #         ).first()

#                 #         if not google_account:
#                 #             return Response(
#                 #                 {"error": "Google Ads not connected for this clinic"},
#                 #                 status=400
#                 #             )

#                 #         google_payload = {
#                 #             "event": "google_ads_campaign_created",
#                 #             "campaign_id": str(campaign.id),
#                 #             "platform": "google_ads",

#                 #             "auth": {
#                 #                 "access_token": google_account.access_token,
#                 #                 "customer_id": getattr(google_account, "customer_id", None),
#                 #             },

#                 #             "campaign": campaign.platform_data.get("google_ads", {})
#                 #         }

#                 #         print("=" * 60)
#                 #         print("GOOGLE ADS PAYLOAD:", google_payload)
#                 #         print("=" * 60)

#                 #         # Send to Zapier
#                 #         send_to_zapier_social(google_payload)
             
             
#             # =====================================================
#             # Define these BEFORE the platform blocks (add at top of the for loop)
#             # =====================================================
#             fb_post_id = None
#             formatted_message = ""
#             google_result = {}   
                
#             # =====================================================
#             # FACEBOOK
#             # =====================================================
#             if "facebook" in channels:

#                 if not facebook_message:
#                     facebook_message = campaign.campaign_name

#                 formatted_message = (
#                     f"📢 {campaign.campaign_name}\n\n"
#                     f"{facebook_message}\n\n"
#                     f"📅 Campaign Duration: "
#                     f"{campaign.start_date.strftime('%d %b %Y')} – "
#                     f"{campaign.end_date.strftime('%d %b %Y')}\n"
#                     f"⏰ Scheduled Time: "
#                     f"{campaign.enter_time.strftime('%I:%M %p') if campaign.enter_time else 'N/A'}\n"
#                     f"🎯 Objective: {campaign.campaign_objective}\n"
#                     f"👥 Target Audience: {campaign.target_audience}\n\n"
#                     f"#LMS #Campaign #{campaign.campaign_name.replace(' ', '')}"
#                 )

#                 social_fb = SocialAccount.objects.filter(
#                     clinic_id=clinic_id, platform="facebook", is_active=True
#                 ).first()

#                 if not social_fb:
#                     return Response(
#                         {"error": "Facebook not connected for this clinic"},
#                         status=400,
#                     )

#                 send_to_zapier_social({
#                     "event": "social_campaign_created",
#                     "campaign_id": str(campaign.id),
#                     "campaign_name": campaign.campaign_name,
#                     "platforms": channels,
#                     "budget": filtered_budget,
#                     "content": facebook_message,
#                     "image_url": campaign.image_url,
#                     "status": data.get("status"),
#                     "start_date": str(data.get("start_date")),
#                     "end_date": str(data.get("end_date")),
#                 })

#                 fb_response = post_to_facebook(
#                     page_id=social_fb.page_id,
#                     page_token=social_fb.access_token,
#                     message=formatted_message,
#                     image_url=campaign.image_url,
#                 )

#                 fb_post_id = fb_response.get("post_id") or fb_response.get("id")

#                 if fb_post_id:
#                     campaign.post_id = fb_post_id
#                     campaign.save(update_fields=["post_id"])


#             # =====================================================
#             # INSTAGRAM
#             # =====================================================
#             if "instagram" in channels:

#                 social_ig = SocialAccount.objects.filter(
#                     clinic_id=clinic_id, platform="facebook", is_active=True
#                 ).first()

#                 ig_user_id = getattr(social_ig, "instagram_id", None)

#                 if social_ig and ig_user_id and campaign.image_url:
#                     post_to_instagram(
#                         ig_user_id=ig_user_id,
#                         access_token=social_ig.access_token,
#                         message=formatted_message,
#                         image_url=campaign.image_url,
#                     )


#             # =====================================================
#             # LINKEDIN
#             # =====================================================
#             if "linkedin" in channels:

#                 social_li = SocialAccount.objects.filter(
#                     clinic_id=clinic_id, platform="linkedin", is_active=True
#                 ).first()

#                 if social_li:
#                     post_to_linkedin(
#                         access_token=social_li.linkedin_token,
#                         author_urn=social_li.linkedin_urn,
#                         message=formatted_message,
#                         image_url=campaign.image_url,
#                     )


#             # =====================================================
#             # GOOGLE ADS (FIXED POSITION ✅)
#             # =====================================================
#             if "google_ads" in channels:
 
#                 google_account = SocialAccount.objects.filter(
#                     clinic_id=clinic_id,
#                     platform="google",
#                     is_active=True
#                 ).first()
 
#                 if not google_account:
#                     return Response(
#                         {"error": "Google Ads not connected for this clinic. "
#                                   "Please connect via /api/auth/google/"},
#                         status=400
#                     )
 
#                 refresh_token = google_account.user_token
#                 if not refresh_token:
#                     return Response(
#                         {"error": "Google refresh token missing. "
#                                   "Please reconnect your Google account."},
#                         status=400
#                     )
 
#                 # --- Build auth from settings + SocialAccount ---
#                 google_auth = {
#                     "developer_token":   settings.GOOGLE_ADS_DEVELOPER_TOKEN,
#                     "client_id":         settings.GOOGLE_CLIENT_ID,
#                     "client_secret":     settings.GOOGLE_CLIENT_SECRET,
#                     "refresh_token":     refresh_token,
#                     "customer_id":       str(
#                         campaign.platform_data.get("google_ads", {}).get("customer_id", "")
#                     ).replace("-", ""),
#                     "login_customer_id": getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", None),
#                 }
 
#                 # --- Build campaign dict from platform_data ---
#                 google_campaign_data = campaign.platform_data.get("google_ads", {})
#                 google_campaign = {
#                     "campaign_name":    campaign.campaign_name,
#                     "budget":           google_campaign_data.get("budget", 500),
#                     "bidding_strategy": google_campaign_data.get("bidding_strategy", "MANUAL_CPC"),
#                     "locations":        google_campaign_data.get("locations", []),
#                     "keywords":         google_campaign_data.get("keywords", []),
#                     "ad_group": {
#                         "name":    google_campaign_data.get("ad_group_name",
#                                        f"{campaign.campaign_name} AdGroup"),
#                         "cpc_bid": google_campaign_data.get("cpc_bid", 20),
#                     },
#                     "ads": google_campaign_data.get("ads", [
#                         {
#                             "headline_1":    campaign.campaign_name[:30],
#                             "headline_2":    "Learn More",
#                             "headline_3":    "Contact Us Today",
#                             "description":   (campaign.campaign_content or "")[:90],
#                             "description_2": "Call us now or visit our website.",
#                             "final_url":     google_campaign_data.get(
#                                                  "final_url", "https://example.com"
#                                              ),
#                         }
#                     ]),
#                 }
 
#                 # --- Call the Google Ads service ---
#                 google_result = create_google_ads_campaign(google_auth, google_campaign)
 
#                 logger.info("[SocialCampaign] Google Ads result: %s", google_result)
 
#                 if google_result.get("status") == "success":
#                     # Persist the resource name back into platform_data
#                     updated_platform_data = campaign.platform_data or {}
#                     updated_platform_data["google_ads"] = {
#                         **updated_platform_data.get("google_ads", {}),
#                         "campaign_resource_name": google_result.get("campaign_resource_name"),
#                         "ad_group_resource_name": google_result.get("ad_group_resource_name"),
#                         "ad_resource_name":        google_result.get("ad_resource_name"),
#                     }
#                     campaign.platform_data = updated_platform_data
#                     campaign.save(update_fields=["platform_data"])
#                 else:
#                     logger.error(
#                         "[SocialCampaign] Google Ads failed: %s",
#                         google_result.get("message")
#                     )
#                     # Non-fatal: log the error but continue (don't block other platforms)
#                     # Change to return Response(...) if you want hard failure instead
 
#                 created_campaigns.append({
#                     "campaign_id":          str(campaign.id),
#                     "mode":                 mode,
#                     "platforms":            channels,
#                     "fb_post_id":           fb_post_id,
#                     "fb_campaign_id":       getattr(campaign, "fb_campaign_id", None),
#                     "google_ads_status":    google_result.get("status") if "google_ads" in channels else None,
#                     "google_campaign_name": google_result.get("campaign_resource_name") if "google_ads" in channels else None,
#                 })
        

#             return Response(
#                 {
#                     "message": "Social media campaign(s) created successfully",
#                     "campaigns": created_campaigns,
#                 },
#                 status=status.HTTP_201_CREATED,
#             )

#         except Exception as e:
#             return Response(
#                 {
#                     "error": str(e),
#                     "type": type(e).__name__,
#                     "trace": traceback.format_exc(),
#                 },
#                 status=400,
#             )


# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback
import requests

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Campaign, CampaignSocialMediaConfig, Clinic
from restapi.models.social_account import SocialAccount
from restapi.services.campaign_social_post_service import _is_direct_image_url
from restapi.serializers.campaign_serializer import SocialMediaCampaignSerializer

from restapi.services.campaign_social_post_service import (
    post_to_facebook,
    post_to_instagram,
    post_to_linkedin,
)
# from restapi.services.google_ads_service import create_google_ads_campaign
from restapi.services.zapier_service import send_to_zapier_social
from restapi.utils.clinic_scope import resolve_request_clinic

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Social Media Campaign Create API View (POST)
# -------------------------------------------------------------------
class SocialMediaCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Social Media Campaign Only",
        request_body=SocialMediaCampaignSerializer,
        responses={
            201: "Campaign Created Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Social Media Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            clinic = resolve_request_clinic(request, required=True)
            print("SOCIAL DATA:", request.data)
            payload = request.data.copy()
            payload["clinic"] = clinic.id
            serializer = SocialMediaCampaignSerializer(data=payload)
            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data

            mode_mapping = {
                "organic_posting": Campaign.ORGANIC,
                "paid_advertising": Campaign.PAID,
            }

            created_campaigns = []

            for mode in data["campaign_mode"]:

                raw_platform_data = data.get("platform_data") or {}
                raw_campaign_content = (data.get("campaign_content") or "").strip()

                # Helper: extract first image URL from mixed text+URL string
                def _extract_image_url(text):
                    if not text:
                        return None, text
                    text = text.strip()
                    # Case 1: entire string is just a URL
                    if (
                        _is_direct_image_url(text)
                        and "\n" not in text
                        and " " not in text
                    ):
                        return text, ""
                    # Case 2: URL embedded inside text
                    tokens = text.replace("\n", " ").split()
                    for token in tokens:
                        token = token.strip(".,;!?\"'")
                        if _is_direct_image_url(token):
                            clean = text.replace(token, "").strip().strip(".,;!?\n ")
                            return token, clean
                    return None, text

                # Resolve facebook message text
                _platform_facebook = strip_tags(
                    raw_platform_data.get("facebook", "") or ""
                ).strip()
                _campaign_content = strip_tags(raw_campaign_content).strip()

                # Extract any embedded image URL from the text fields
                _fb_extracted_url, _platform_facebook = _extract_image_url(
                    _platform_facebook
                )
                _cc_extracted_url, _campaign_content = _extract_image_url(
                    _campaign_content
                )

                facebook_message = _platform_facebook or _campaign_content

                # Resolve image_url
                _raw_image_url = (request.data.get("image_url") or "").strip()
                if _raw_image_url:
                    _extracted, _ = _extract_image_url(_raw_image_url)
                    image_url_field = _extracted or None
                    if image_url_field != _raw_image_url:
                        print(
                            f"image_url cleaned: {repr(_raw_image_url[:80])} -> {image_url_field}"
                        )
                else:
                    image_url_field = None

                if not image_url_field and _fb_extracted_url:
                    image_url_field = _fb_extracted_url
                    print(f"image_url extracted from platform_data.facebook: {image_url_field}")

                if not image_url_field and _cc_extracted_url:
                    image_url_field = _cc_extracted_url
                    print(f"image_url extracted from campaign_content: {image_url_field}")

                print("=" * 60)
                print("DEBUG raw platform_data   :", raw_platform_data)
                print("DEBUG campaign_content     :", _campaign_content)
                print("DEBUG facebook_message     :", facebook_message)
                print("DEBUG image_url            :", image_url_field)
                print("=" * 60)

                # Build selected_start / selected_end
                from datetime import datetime, time, date as date_type

                start = data["start_date"]
                end = data["end_date"]

                selected_start = timezone.make_aware(
                    datetime.combine(
                        (
                            start
                            if isinstance(start, date_type)
                            else datetime.strptime(start, "%Y-%m-%d").date()
                        ),
                        time(0, 0, 0),
                    )
                )
                selected_end = timezone.make_aware(
                    datetime.combine(
                        (
                            end
                            if isinstance(end, date_type)
                            else datetime.strptime(end, "%Y-%m-%d").date()
                        ),
                        time(23, 59, 59),
                    )
                )

                # Only store budget for selected platforms
                selected_platforms = data["select_ad_accounts"]
                raw_budget_data = data.get("budget_data") or {}
                filtered_budget = {
                    p: raw_budget_data.get(p, 0) for p in selected_platforms
                }
                filtered_budget["total"] = sum(
                    v for k, v in filtered_budget.items() if k != "total"
                )

                campaign = Campaign.objects.create(
                    clinic_id=data["clinic"],
                    campaign_name=data["campaign_name"],
                    campaign_description=data["campaign_description"],
                    campaign_objective=data["campaign_objective"],
                    target_audience=data["target_audience"],
                    start_date=data["start_date"],
                    end_date=data["end_date"],
                    campaign_mode=mode_mapping.get(mode),
                    campaign_content=facebook_message,
                    selected_start=selected_start,
                    selected_end=selected_end,
                    enter_time=data["enter_time"],
                    platform_data=raw_platform_data,
                    budget_data=filtered_budget,
                    image_url=image_url_field,
                    is_active=True,
                )

                print("=" * 60)
                print("PLATFORM DATA:", campaign.platform_data)
                print("FACEBOOK MESSAGE:", facebook_message)
                print("IMAGE URL SAVED:", campaign.image_url)
                print("=" * 60)

                channels = []

                for platform in data["select_ad_accounts"]:
                    CampaignSocialMediaConfig.objects.create(
                        campaign=campaign,
                        platform_name=platform,
                        is_active=True,
                    )
                    channels.append(platform)

                clinic_id = data["clinic"]

                # Defaults — must be set before platform blocks
                fb_post_id = None
                formatted_message = ""
                google_result = {}

                # =====================================================
                # FACEBOOK
                # =====================================================
                if "facebook" in channels:

                    if not facebook_message:
                        facebook_message = campaign.campaign_name

                    formatted_message = (
                        f"📢 {campaign.campaign_name}\n\n"
                        f"{facebook_message}\n\n"
                        f"📅 Campaign Duration: "
                        f"{campaign.start_date.strftime('%d %b %Y')} – "
                        f"{campaign.end_date.strftime('%d %b %Y')}\n"
                        f"⏰ Scheduled Time: "
                        f"{campaign.enter_time.strftime('%I:%M %p') if campaign.enter_time else 'N/A'}\n"
                        f"🎯 Objective: {campaign.campaign_objective}\n"
                        f"👥 Target Audience: {campaign.target_audience}\n\n"
                        f"#LMS #Campaign #{campaign.campaign_name.replace(' ', '')}"
                    )

                    social_fb = SocialAccount.objects.filter(
                        clinic_id=clinic_id, platform="facebook", is_active=True
                    ).first()

                    if not social_fb:
                        return Response(
                            {"error": "Facebook not connected for this clinic"},
                            status=400,
                        )

                    send_to_zapier_social({
                        "event": "social_campaign_created",
                        "campaign_id": str(campaign.id),
                        "campaign_name": campaign.campaign_name,
                        "platforms": channels,
                        "budget": filtered_budget,
                        "content": facebook_message,
                        "image_url": campaign.image_url,
                        "status": data.get("status"),
                        "start_date": str(data.get("start_date")),
                        "end_date": str(data.get("end_date")),
                    })

                    fb_response = post_to_facebook(
                        page_id=social_fb.page_id,
                        page_token=social_fb.access_token,
                        message=formatted_message,
                        image_url=campaign.image_url,
                    )

                    fb_post_id = fb_response.get("post_id") or fb_response.get("id")

                    if fb_post_id:
                        campaign.post_id = fb_post_id
                        campaign.save(update_fields=["post_id"])

                # =====================================================
                # INSTAGRAM
                # =====================================================
                if "instagram" in channels:

                    social_ig = SocialAccount.objects.filter(
                        clinic_id=clinic_id, platform="facebook", is_active=True
                    ).first()

                    ig_user_id = getattr(social_ig, "instagram_id", None)

                    if social_ig and ig_user_id and campaign.image_url:
                        post_to_instagram(
                            ig_user_id=ig_user_id,
                            access_token=social_ig.access_token,
                            message=formatted_message,
                            image_url=campaign.image_url,
                        )

                # =====================================================
                # LINKEDIN
                # =====================================================
                if "linkedin" in channels:

                    social_li = SocialAccount.objects.filter(
                        clinic_id=clinic_id, platform="linkedin", is_active=True
                    ).first()

                    if social_li:
                        post_to_linkedin(
                            access_token=social_li.linkedin_token,
                            author_urn=social_li.linkedin_urn,
                            message=formatted_message,
                            image_url=campaign.image_url,
                        )

                # =====================================================
                # GOOGLE ADS
                # =====================================================
                if "google_ads" in channels:

                    print("=" * 60)
                    print("DEBUG: ENTERING GOOGLE ADS BLOCK")
                    print("DEBUG: channels =", channels)
                    print("=" * 60)

                    google_account = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="google",
                        is_active=True
                    ).first()

                    # --- Load tokens: DB first, then settings.py fallback ---
                    refresh_token = google_account.user_token if google_account else None
                    access_token  = google_account.access_token if google_account else None
                    customer_id   = google_account.customer_id if google_account else None

                    if not refresh_token:
                        refresh_token = getattr(settings, "GOOGLE_REFRESH_TOKEN", None)

                    if not access_token:
                        access_token = getattr(settings, "GOOGLE_ACCESS_TOKEN", None)

                    if not customer_id:
                        customer_id = getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", None)

                    if not refresh_token:
                        logger.error(
                            "[SocialCampaign] Google Ads skipped — refresh token missing for clinic %s",
                            clinic_id
                        )
                        google_result = {"status": "skipped_no_token"}
                    else:
                        # ✅ FIX: Get clinic website for final_url
                        clinic_obj = Clinic.objects.filter(id=clinic_id).first()
                        clinic_website = (
                            getattr(clinic_obj, "website", None)
                            or getattr(clinic_obj, "clinic_url", None)
                            or settings.BACKEND_BASE_URL
                        )

                        # platform_data.google_ads can be a string or a dict
                        raw_google_data = campaign.platform_data.get("google_ads", {})

                        if isinstance(raw_google_data, str):
                            google_ads_description = raw_google_data
                            google_campaign_data   = {}
                        else:
                            google_ads_description = ""
                            google_campaign_data   = raw_google_data

                        # Resolve image_url
                        image_url = (
                            google_campaign_data.get("image_url")
                            or campaign.image_url
                            or None
                        )

                        # Resolve budget
                        budget = int(
                            filtered_budget.get("google_ads")
                            or google_campaign_data.get("budget", 500)
                        )

                        # Keywords
                        keywords_raw = google_campaign_data.get("keywords", [])
                        keywords_str = (
                            ",".join(keywords_raw)
                            if isinstance(keywords_raw, list)
                            else str(keywords_raw)
                        )

                        google_payload = {
                            "event":              "google_ads_campaign_created",
                            "campaign_name":      campaign.campaign_name,
                            "image_url":          image_url or "",
                            "customer_id":        str(customer_id or "").replace("-", ""),
                            "login_customer_id":  getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
                            "developer_token":    settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                            "client_id":          settings.GOOGLE_CLIENT_ID,
                            "client_secret":      settings.GOOGLE_CLIENT_SECRET,
                            "refresh_token":      refresh_token,
                            "access_token":       access_token or "",
                            "budget":             budget,
                            "bidding_strategy":   google_campaign_data.get("bidding_strategy", "MANUAL_CPC"),
                            "locations":          google_campaign_data.get("locations", []),
                            "keywords":           keywords_str,
                            "cpc_bid":            int(google_campaign_data.get("cpc_bid", 20)),
                            "ad_group_name":      google_campaign_data.get(
                                                      "ad_group_name",
                                                      f"{campaign.campaign_name} AdGroup"
                                                  ),
                            # ✅ FIX: use clinic website instead of hardcoded example.com
                            "final_url":          clinic_website,
                            # ✅ FIX: auto headlines from campaign data
                            "headline_1":         campaign.campaign_name[:30],
                            "headline_2":         "Book Free Consultation",
                            "headline_3":         "Contact Us Today",
                            # ✅ FIX: use campaign_description instead of emoji content
                            "description":        (campaign.campaign_description or campaign.campaign_name)[:90],
                            "description_2":      "Expert care tailored for you. Call now.",
                            "campaign_objective": campaign.campaign_objective,
                            "start_date":         str(campaign.start_date),
                            "end_date":           str(campaign.end_date),
                            # ✅ FIX: add campaign_id and callback_url for insights flow
                            "campaign_id":        str(campaign.id),
                            "callback_url":       f"{settings.BACKEND_BASE_URL}/api/campaign/insights/callback/",
                        }

                        print("=" * 60)
                        print("GOOGLE ADS PAYLOAD SENDING TO ZAPIER:", google_payload)
                        print("=" * 60)

                        webhook_url = settings.ZAPIER_WEBHOOK_GOOGLE_ADS_URL
                        try:
                            zapier_resp = requests.post(
                                webhook_url, json=google_payload, timeout=10
                            )
                            logger.info(
                                "[SocialCampaign] Google Ads Zapier response: %s | body: %s",
                                zapier_resp.status_code, zapier_resp.text
                            )
                            google_result = {
                                "status":        "sent_to_zapier",
                                "zapier_status": zapier_resp.status_code,
                            }
                        except requests.exceptions.RequestException as e:
                            logger.error(
                                "[SocialCampaign] Google Ads Zapier request failed: %s", str(e)
                            )
                            google_result = {"status": "zapier_failed", "error": str(e)}

                # =====================================================
                # APPEND RESULT
                # =====================================================
                created_campaigns.append({
                    "campaign_id":          str(campaign.id),
                    "mode":                 mode,
                    "platforms":            channels,
                    "fb_post_id":           fb_post_id,
                    "fb_campaign_id":       getattr(campaign, "fb_campaign_id", None),
                    "google_ads_status":    google_result.get("status") if "google_ads" in channels else None,
                    "google_campaign_name": google_result.get("campaign_resource_name") if "google_ads" in channels else None,
                })

            # =====================================================
            # RETURN
            # =====================================================
            return Response(
                {
                    "message": "Social media campaign(s) created successfully",
                    "campaigns": created_campaigns,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "type": type(e).__name__,
                    "trace": traceback.format_exc(),
                },
                status=400,
            )