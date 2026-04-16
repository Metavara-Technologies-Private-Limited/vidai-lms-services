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

from restapi.models import Campaign, CampaignSocialMediaConfig
from restapi.models.social_account import SocialAccount
from restapi.services.campaign_social_post_service import _is_direct_image_url
from restapi.serializers.campaign_serializer import SocialMediaCampaignSerializer

from restapi.services.campaign_social_post_service import (
    post_to_facebook,
    post_to_instagram,
    post_to_linkedin,
)
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
                # Priority: 1. Explicit image_url field  2. platform_data.facebook  3. campaign_content
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
                    print(
                        f"image_url extracted from platform_data.facebook: {image_url_field}"
                    )

                if not image_url_field and _cc_extracted_url:
                    image_url_field = _cc_extracted_url
                    print(
                        f"image_url extracted from campaign_content: {image_url_field}"
                    )

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
                # Previously: budget_data=data.get("budget_data") or {}
                # stored ALL platforms (instagram/facebook/linkedin)
                # even when only 2 were selected — causing wrong totals.
                # Now we filter to only the selected platforms + recompute total.
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

                # social = SocialAccount.objects.filter(
                #     clinic_id=clinic_id,
                #     platform="facebook",
                #     is_active=True
                # ).first()

                # fb_post_id = None

                # print("=" * 60)
                # print("CHANNELS:", channels)
                # print("SOCIAL ACCOUNT FOUND:", social)
                # print("=" * 60)

                if "facebook" in channels:
                    # if not social:
                    #     print("NO FACEBOOK SOCIAL ACCOUNT for clinic_id:", clinic_id)
                    #     return Response(
                    #         {"error": "Facebook not connected for this clinic"},
                    #         status=400
                    #     )

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

                    fb_post_id = None

                    print("=" * 60)
                    print("CHANNELS:", channels)
                    print("FORMATTED MESSAGE:", formatted_message[:80], "...")
                    print("=" * 60)

                    if "facebook" in channels:
                        social_fb = SocialAccount.objects.filter(
                            clinic_id=clinic_id, platform="facebook", is_active=True
                        ).first()

                        if not social_fb:
                            print(
                                "NO FACEBOOK SOCIAL ACCOUNT for clinic_id:", clinic_id
                            )
                            return Response(
                                {"error": "Facebook not connected for this clinic"},
                                status=400,
                            )

                        print(">>> CALLING post_to_facebook()")
                        print("Page ID   :", social_fb.page_id)
                        print("Page Name :", social_fb.page_name)
                        print(
                            "Token (20):",
                            (
                                social_fb.access_token[:20]
                                if social_fb.access_token
                                else "NONE"
                            ),
                        )
                        print("Image URL :", campaign.image_url)

                        send_to_zapier_social(
                            {
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
                            }
                        )

                        fb_response = post_to_facebook(
                            page_id=social_fb.page_id,
                            page_token=social_fb.access_token,
                            message=formatted_message,
                            image_url=campaign.image_url,
                        )

                        print("FB POST FULL RESPONSE:", fb_response)
                        # Use post_id (full page_post format) if available, else fall back to id
                        fb_post_id = fb_response.get("post_id") or fb_response.get("id")
                        print("FB POST ID:", fb_post_id)

                        if fb_post_id:
                            campaign.post_id = fb_post_id
                            campaign.save(update_fields=["post_id"])
                            print("FB POST ID SAVED:", fb_post_id)
                        else:
                            print("FB POST ID IS NONE — check FB error above")

                        # =====================================================
                        # CREATE FACEBOOK AD CAMPAIGN (Paid mode only)
                        # =====================================================
                        if "facebook" in channels:
                            try:
                                fb_budget = filtered_budget.get("facebook", 200)
                                fb_camp_r = requests.post(
                                    f"https://graph.facebook.com/v19.0/act_{settings.FB_AD_ACCOUNT_ID}/campaigns",
                                    data={
                                        "name": campaign.campaign_name,
                                        "objective": "OUTCOME_LEADS",
                                        "status": "PAUSED",
                                        "daily_budget": int(fb_budget) * 100,
                                        "special_ad_categories": "[]",
                                        "is_adset_budget_sharing_enabled": False,
                                        "access_token": settings.FB_ACCESS_TOKEN,
                                    }
                                )
                                fb_camp_data = fb_camp_r.json()
                                if "id" in fb_camp_data:
                                    campaign.fb_campaign_id = fb_camp_data["id"]
                                    campaign.save(update_fields=["fb_campaign_id"])
                                    print("FB AD CAMPAIGN CREATED:", fb_camp_data["id"])
                                else:
                                    print("FB AD CAMPAIGN ERROR:", fb_camp_data)
                            except Exception:
                                print("FB AD CAMPAIGN FAILED:\n" + traceback.format_exc())

                    if "instagram" in channels:
                        if not campaign.image_url:
                            print(
                                "Skipping Instagram: image_url is required for Instagram posts"
                            )
                        else:
                            social_ig = SocialAccount.objects.filter(
                                clinic_id=clinic_id, platform="facebook", is_active=True
                            ).first()

                            ig_user_id = getattr(social_ig, "instagram_id", None)

                            if not social_ig or not ig_user_id:
                                print(
                                    "Instagram not connected or instagram_id missing on SocialAccount"
                                )
                            else:
                                print(">>> CALLING post_to_instagram()")
                                print("IG User ID :", ig_user_id)
                                ig_response = post_to_instagram(
                                    ig_user_id=ig_user_id,
                                    access_token=social_ig.access_token,
                                    message=formatted_message,
                                    image_url=campaign.image_url,
                                )
                                print("IG POST RESPONSE:", ig_response)

                    if "linkedin" in channels:
                        social_li = SocialAccount.objects.filter(
                            clinic_id=clinic_id, platform="linkedin", is_active=True
                        ).first()

                        if not social_li:
                            print("LinkedIn not connected for clinic_id:", clinic_id)
                        else:
                            print(">>> CALLING post_to_linkedin()")
                            print("Author URN :", social_li.linkedin_urn)
                            li_response = post_to_linkedin(
                                access_token=social_li.linkedin_token,
                                author_urn=social_li.linkedin_urn,
                                message=formatted_message,
                                image_url=campaign.image_url,
                            )
                            print("LI POST RESPONSE:", li_response)

                created_campaigns.append(
    {
        "campaign_id": str(campaign.id),
        "mode": mode,
        "platforms": channels,
        "fb_post_id": fb_post_id,
        "fb_campaign_id": campaign.fb_campaign_id,
    }
)

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
