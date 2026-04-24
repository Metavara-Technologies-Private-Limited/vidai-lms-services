# restapi\views\social_campaign_views.py
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
from rest_framework.permissions import IsAuthenticated

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Campaign, CampaignSocialMediaConfig
from restapi.models.social_account import SocialAccount
from restapi.services.campaign_social_post_service import _is_direct_image_url
from restapi.serializers.campaign_serializer import SocialMediaCampaignSerializer

from restapi.services.campaign_social_post_service import (
    post_to_facebook,
    post_to_instagram,
    post_to_linkedin,
)
# from restapi.services.google_ads_service import create_google_ads_campaign
from restapi.services.payload_builders import LinkedInPayloadBuilder
from restapi.services.zapier_service import send_to_zapier_social

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
            print("SOCIAL DATA:", request.data)
            serializer = SocialMediaCampaignSerializer(data=request.data)
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
                # Priority: 1. Explicit image_url field  2. platform_data.facebook  3. campaign_content
                # _raw_image_url = (request.data.get("image_url") or "").strip()
                _raw_image_url = (request.data.get("image_url") or "").strip()
                image_url_field = _raw_image_url if _raw_image_url else None

                # Fallback to URLs extracted from text fields only
                if not image_url_field and _fb_extracted_url:
                    image_url_field = _fb_extracted_url
                    print(f"image_url extracted from platform_data.facebook: {image_url_field}")

                if not image_url_field and _cc_extracted_url:
                    image_url_field = _cc_extracted_url
                    print(f"image_url extracted from campaign_content: {image_url_field}")
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

                # =====================================================
                # FIX: Only store budget for SELECTED platforms
                # =====================================================
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

                # =====================================================
                # Defaults — must be set before platform blocks
                # =====================================================
                fb_post_id = None
                google_result = {}

                # =====================================================
                # FIX 1: Build formatted_message ONCE here, for ALL platforms
                # =====================================================
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

                # =====================================================
                # FACEBOOK
                # =====================================================
                if "facebook" in channels:

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
                # LINKEDIN VIA ZAPIER
                # =====================================================

                if "linkedin" in channels:

                    social_li = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="linkedin",
                        is_active=True
                    ).first()

                    if not social_li or not social_li.access_token:
                        return Response(
                            {"error":"LinkedIn not connected"},
                            status=400
                        )

                    if (
                        not social_li.account_id
                        or not social_li.org_urn
                        or not social_li.campaign_group
                    ):
                        return Response(
                            {
                                "error":
                                "LinkedIn account setup incomplete"
                            },
                            status=400
                        )


                    linkedin_payload = LinkedInPayloadBuilder.create(
                        campaign=campaign,
                        social_account=social_li,
                        validated_data=data
                    )


                    print("🚀 Sending LinkedIn Campaign To Zapier")
                    print({
                        **linkedin_payload,
                        "auth":{
                            **linkedin_payload["auth"],
                            "access_token":"****"
                        }
                    })

                    send_to_zapier_social(linkedin_payload)

                    print("✅ Sent To Zapier")
                
                
                    
                # =====================================================
                # GOOGLE ADS
                # =====================================================
                if "google_ads" in channels:

                    google_account = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="google",
                        is_active=True
                    ).first()

                    if not google_account:
                        return Response(
                            {"error": "Google Ads not connected for this clinic. "
                                      "Please connect via /api/auth/google/"},
                            status=400
                        )

                    refresh_token = google_account.user_token
                    if not refresh_token:
                        return Response(
                            {"error": "Google refresh token missing. "
                                      "Please reconnect your Google account."},
                            status=400
                        )

                    google_campaign_data = campaign.platform_data.get("google_ads", {})

                    # --- IMAGE LOGIC ---
                    # Check if the user provided an image_url explicitly in platform_data, 
                    # otherwise fallback to checking if the campaign_content itself is an image URL.
                    image_url = google_campaign_data.get("image_url")
                    if not image_url and _is_direct_image_url(campaign.campaign_content):
                        image_url = campaign.campaign_content

                    keywords_raw = google_campaign_data.get("keywords", [])
                    keywords_str = (
                        ",".join(keywords_raw)
                        if isinstance(keywords_raw, list)
                        else str(keywords_raw)
                    )

                    google_payload = {
                        "event":             "google_ads_campaign_created",
                        "campaign_name":     campaign.campaign_name,
                        "image_url":         image_url,
                        "customer_id":       str(google_campaign_data.get("customer_id", "")).replace("-", ""),
                        "login_customer_id": getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""),
                        "developer_token":   settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                        "client_id":         settings.GOOGLE_CLIENT_ID,
                        "client_secret":     settings.GOOGLE_CLIENT_SECRET,
                        "refresh_token":     refresh_token,
                        "budget":            google_campaign_data.get("budget", 500),
                        "bidding_strategy":  google_campaign_data.get("bidding_strategy", "MANUAL_CPC"),
                        "locations":         google_campaign_data.get("locations", []),
                        "keywords":          keywords_str,
                        "cpc_bid":           google_campaign_data.get("cpc_bid", 20),
                        "ad_group_name":     google_campaign_data.get("ad_group_name", f"{campaign.campaign_name} AdGroup"),
                        "final_url":         google_campaign_data.get("final_url", "https://example.com"),
                        "headline_1":        campaign.campaign_name[:30],
                        "headline_2":        "Learn More",
                        "headline_3":        "Contact Us Today",
                        "description":       (campaign.campaign_content or "")[:90],
                        "description_2":     "Call us now or visit our website.",
                    }

                    send_to_zapier_social(google_payload)
                    google_result = {"status": "sent_to_zapier"}

                # =====================================================
                # APPEND RESULT — outside all platform if-blocks,
                # still inside the "for mode in data['campaign_mode']" loop
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
            # RETURN — outside the for loop, inside try
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
            
            
# -------------------------------------------------------------------
# LINKEDIN CAMPAIGN INSIGHTS
# POST /api/social/campaign/insights/
# -------------------------------------------------------------------
class LinkedInCampaignInsightsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:
            campaign_id = request.data.get(
                "campaign_id"
            )

            platform = request.data.get(
                "platform",
                "linkedin"
            )

            if platform != "linkedin":
                return Response(
                    {
                        "error":
                        "Only linkedin supported currently"
                    },
                    status=400
                )

            if not campaign_id:
                return Response(
                    {
                        "error":
                        "campaign_id required"
                    },
                    status=400
                )


            # -----------------------------------
            # Load campaign
            # -----------------------------------
            campaign = Campaign.objects.get(
                id=campaign_id
            )
            
            # -----------------------------------
            # Do not fetch insights before launch
            # -----------------------------------
            if campaign.start_date > timezone.now().date():
                return Response(
                    {
                        "error":
                        "Campaign has not started yet. "
                        "Insights unavailable."
                    },
                    status=400
                )

            if not campaign.linkedin_external_campaign_id:
                return Response(
                    {
                      "error":
                      "LinkedIn campaign not synced yet"
                    },
                    status=400
                )


            # -----------------------------------
            # Get linkedin account
            # -----------------------------------
            social_li = SocialAccount.objects.filter(
                clinic=campaign.clinic,
                platform="linkedin",
                is_active=True
            ).first()

            if not social_li:
                return Response(
                    {
                     "error":
                     "LinkedIn account not connected"
                    },
                    status=400
                )


            # -----------------------------------
            # Build INSIGHTS payload
            # -----------------------------------
            payload = LinkedInPayloadBuilder.insights(
                campaign,
                social_li
            )


            print("📊 Sending Insights Payload")
            print(payload)


            send_to_zapier_social(
                payload
            )


            return Response(
                {
                    # "status":"sent",
                    "status":"insights_requested",
                    "action":"INSIGHTS",
                    "campaign_id": str(
                        campaign.id
                    ),
                    "linkedin_campaign_id":
                        campaign.linkedin_external_campaign_id
                },
                status=200
            )


        except Campaign.DoesNotExist:
            return Response(
                {"error":"Campaign not found"},
                status=404
            )

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "trace":
                        traceback.format_exc()
                },
                status=400
            )
            
# -------------------------------------------------------------------
# LINKEDIN CAMPAIGN STATUS
# POST /api/social/campaign/status/
# -------------------------------------------------------------------
class LinkedInCampaignStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:
            campaign_id = request.data.get(
                "campaign_id"
            )

            platform = request.data.get(
                "platform",
                "linkedin"
            )

            if platform != "linkedin":
                return Response(
                    {
                      "error":
                      "Only linkedin supported currently"
                    },
                    status=400
                )

            if not campaign_id:
                return Response(
                    {
                      "error":
                      "campaign_id required"
                    },
                    status=400
                )


            # -----------------------------
            # Load campaign
            # -----------------------------
            campaign = Campaign.objects.get(
                id=campaign_id
            )

            if not campaign.linkedin_external_campaign_id:
                return Response(
                    {
                      "error":
                      "LinkedIn campaign not synced yet"
                    },
                    status=400
                )


            # -----------------------------
            # Get connected LinkedIn account
            # -----------------------------
            social_li = SocialAccount.objects.filter(
                clinic=campaign.clinic,
                platform="linkedin",
                is_active=True
            ).first()

            if not social_li:
                return Response(
                    {
                      "error":
                      "LinkedIn account not connected"
                    },
                    status=400
                )


            # -----------------------------
            # Build STATUS payload
            # -----------------------------
            payload = LinkedInPayloadBuilder.status(
                campaign,
                social_li
            )

            print("📡 Sending Status Payload")
            print(payload)

            send_to_zapier_social(
                payload
            )


            return Response(
                {
                  "status":"status_requested",
                  "action":"STATUS",
                  "campaign_id":str(
                      campaign.id
                  ),
                  "linkedin_campaign_id":
                    campaign.linkedin_external_campaign_id
                },
                status=200
            )


        except Campaign.DoesNotExist:
            return Response(
                {
                  "error":"Campaign not found"
                },
                status=404
            )

        except Exception as e:
            return Response(
                {
                  "error":str(e),
                  "trace":
                    traceback.format_exc()
                },
                status=400
            )            
            
            
class LinkedInCampaignUpdateAPIView(APIView):

    def post(self, request):

        campaign = Campaign.objects.get(
            id=request.data["campaign_id"]
        )

        desired_status = request.data[
            "desired_status"
        ]

        social_account = SocialAccount.objects.get(
            clinic=campaign.clinic,
            platform="linkedin"
        )

        payload = LinkedInPayloadBuilder.update(
            campaign,
            social_account,
            desired_status
        )

        send_to_zapier_social(
            payload
        )

        return Response({
           "status":"update_requested",
           "desired_status":
               desired_status
        })            