# =====================================================
# restapi/views/social_campaign_views.py
# =====================================================

import logging
import traceback
import requests
import math

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from drf_yasg.utils import swagger_auto_schema

from restapi.models import (
    Campaign,
    CampaignSocialMediaConfig,
    Clinic,
)
from restapi.models.social_account import SocialAccount

from restapi.services.campaign_social_post_service import (
    _is_direct_image_url,
    post_to_facebook,
    post_to_instagram,
)

from restapi.serializers.campaign_serializer import (
    SocialMediaCampaignSerializer,
)

from restapi.services.payload_builders import (
    LinkedInPayloadBuilder,
)

from restapi.services.zapier_service import (
    send_to_zapier_social,
)

from restapi.utils.clinic_scope import (
    resolve_request_clinic,
)

logger = logging.getLogger(__name__)

# -----------------------------------
# Campaign Objective Mapping
# -----------------------------------
CAMPAIGN_OBJECTIVES = {
    "awareness": "OUTCOME_AWARENESS",
    "leads": "OUTCOME_LEADS",
}

DEFAULT_CAMPAIGN_IMAGE = "https://images.unsplash.com/photo-1584515933487-779824d29309?q=80&w=1200&auto=format&fit=crop"

def get_usd_to_inr():
    try:
        res = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=INR", timeout=3
        )
        return res.json()["rates"]["INR"]
    except:
        return 95  # fallback

# =====================================================
# SOCIAL MEDIA CAMPAIGN CREATE
# =====================================================
class SocialMediaCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Social Media Campaign Only",
        request_body=SocialMediaCampaignSerializer,
        responses={
            201: "Created",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Social Media Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            clinic = resolve_request_clinic(
                request,
                required=True,
            )

            payload = request.data.copy()
            payload["clinic"] = clinic.id

            serializer = SocialMediaCampaignSerializer(
                data=payload
            )
            serializer.is_valid(
                raise_exception=True
            )

            data = serializer.validated_data

            mode_mapping = {
                "organic_posting": Campaign.ORGANIC,
                "paid_advertising": Campaign.PAID,
            }

            created_campaigns = []

            for mode in data[
                "campaign_mode"
            ]:

                raw_platform_data = (
                    data.get(
                        "platform_data"
                    ) or {}
                )

                raw_campaign_content = (
                    data.get(
                        "campaign_content"
                    ) or ""
                ).strip()

                # -----------------------------------
                # IMAGE URL extractor
                # -----------------------------------
                def _extract_image_url(text):
                    if not text:
                        return None, text

                    text = text.strip()

                    if (
                        _is_direct_image_url(text)
                        and "\n" not in text
                        and " " not in text
                    ):
                        return text, ""

                    tokens = (
                        text.replace(
                            "\n",
                            " ",
                        ).split()
                    )

                    for token in tokens:
                        token = token.strip(
                            ".,;!?\"'"
                        )
                        if _is_direct_image_url(
                            token
                        ):
                            clean = (
                                text.replace(
                                    token,
                                    "",
                                )
                                .strip()
                                .strip(
                                    ".,;!?\n "
                                )
                            )
                            return token, clean

                    return None, text

                platform_fb = strip_tags(
                    raw_platform_data.get(
                        "facebook",
                        "",
                    ) or ""
                ).strip()

                campaign_content = strip_tags(
                    raw_campaign_content
                ).strip()

                fb_url, platform_fb = (
                    _extract_image_url(
                        platform_fb
                    )
                )
                cc_url, campaign_content = (
                    _extract_image_url(
                        campaign_content
                    )
                )

                facebook_message = (
                    platform_fb
                    or campaign_content
                )

                raw_image_url = (
                    request.data.get(
                        "image_url"
                    ) or ""
                ).strip()

                image_url_field = (
                    raw_image_url
                    if raw_image_url
                    else None
                )

                if raw_image_url:
                    extracted, _ = (
                        _extract_image_url(
                            raw_image_url
                        )
                    )
                    image_url_field = (
                        extracted or None
                    )

                if (
                    not image_url_field
                    and fb_url
                ):
                    image_url_field = fb_url

                if (
                    not image_url_field
                    and cc_url
                ):
                    image_url_field = cc_url

                if not image_url_field:
                    image_url_field = DEFAULT_CAMPAIGN_IMAGE

                # -----------------------------------
                # Dates
                # -----------------------------------
                from datetime import (
                    datetime,
                    time,
                    date as date_type,
                )

                start = data[
                    "start_date"
                ]
                end = data[
                    "end_date"
                ]

                # selected_start = (
                #     timezone.make_aware(
                #         datetime.combine(
                #             (
                #                 start
                #                 if isinstance(
                #                     start,
                #                     date_type,
                #                 )
                #                 else datetime.strptime(
                #                     start,
                #                     "%Y-%m-%d",
                #                 ).date()
                #             ),
                #             time(0,0,0),
                #         )
                #     )
                # )
                enter_time = data.get("enter_time")

                parsed_time = (
                    enter_time
                    if isinstance(enter_time, time)
                    else (
                        datetime.strptime(
                            enter_time,
                            "%H:%M",
                        ).time()
                        if enter_time
                        else time(0, 0, 0)
                    )
                )

                naive_start = datetime.combine(
                    (
                        start
                        if isinstance(start, date_type)
                        else datetime.strptime(
                            start,
                            "%Y-%m-%d",
                        ).date()
                    ),
                    parsed_time,
                )

                selected_start = timezone.localtime(
                    timezone.make_aware(
                        naive_start,
                        timezone.get_current_timezone(),
                    )
                )

                naive_end = datetime.combine(
                    (
                        end
                        if isinstance(end, date_type)
                        else datetime.strptime(
                            end,
                            "%Y-%m-%d",
                        ).date()
                    ),
                    time(23, 59, 59),
                )

                selected_end = timezone.localtime(
                    timezone.make_aware(
                        naive_end,
                        timezone.get_current_timezone(),
                    )
                )

                selected_platforms = (
                    data[
                        "select_ad_accounts"
                    ]
                )

                raw_budget = (
                    data.get(
                        "budget_data"
                    ) or {}
                )

                filtered_budget = {
                    p: raw_budget.get(
                        p,
                        0,
                    )
                    for p in selected_platforms
                }

                filtered_budget[
                    "total"
                ] = sum(
                    v
                    for k,v in filtered_budget.items()
                    if k != "total"
                )

                # -----------------------------------
                # Normalize Google Ads platform data
                # -----------------------------------
                google_ads_data = (
                    raw_platform_data.get(
                        "google_ads",
                        {}
                    ) or {}
                )

                if isinstance(google_ads_data, dict):

                    google_ads_data["status"] = (
                        "paused"
                        if str(
                            data.get("status", "")
                        ).lower() in ["paused", "draft"]
                        else "active"
                    )

                    raw_platform_data["google_ads"] = (
                        google_ads_data
                    )

                # -----------------------------------
                # Create campaign
                # -----------------------------------
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
                    status=data["status"],
                    is_active=data.get("is_active", False),
                )

                channels = []

                for platform in data[
                    "select_ad_accounts"
                ]:
                    CampaignSocialMediaConfig.objects.create(
                        campaign=campaign,
                        platform_name=platform,
                        is_active=True,
                    )
                    channels.append(platform)

                clinic_id = data[
                    "clinic"
                ]

                fb_post_id = None
                google_result = {}

                if not facebook_message:
                    facebook_message = (
                        campaign.campaign_name
                    )

                # # ===================================
                # FACEBOOK
                # ===================================
                if "facebook" in channels:

                    social_fb = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="facebook",
                        is_active=True,
                    ).first()

                    if not social_fb:
                        return Response(
                            {"error": "Facebook not connected"},
                            status=400,
                        )

                    if not social_fb.account_id:
                        return Response(
                            {"error": "Facebook ad account not found"},
                            status=400,
                        )

                    status = (
                        "PAUSED"
                        if (campaign.status or "").lower() == "draft"
                        else "ACTIVE"
                    )

                    fb_budget = float(
                        filtered_budget.get("facebook", 2)
                    )

                    usd_to_inr = get_usd_to_inr()
                    fb_daily_budget = math.ceil(
                        (fb_budget * usd_to_inr) * 100
                    )

                    fb_platform_data = raw_platform_data.get(
                        "facebook",
                        {}
                    ) or {}

                    if isinstance(fb_platform_data, dict):
                        facebook_message = fb_platform_data.get(
                            "content",
                            ""
                        )

                        fb_country = fb_platform_data.get(
                            "country_code",
                            "IN"
                        )

                        fb_state = fb_platform_data.get(
                            "state"
                        )

                    else:
                        facebook_message = str(
                            fb_platform_data
                        )

                        fb_country = "IN"

                    facebook_payload = {
                        "event": "meta_ads_create",
                        "platform": "facebook",
                        "schedule_datetime": (
                            campaign.selected_start.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            if campaign.selected_start
                            else None
                        ),
                        "access_token": social_fb.access_token,
                        "ad_account_id": social_fb.account_id,
                        "page_id": social_fb.page_id,
                        "campaign": {
                            "internal_campaign_id": str(campaign.id),
                            "name": f"{campaign.campaign_name}",
                            "objective": CAMPAIGN_OBJECTIVES.get(
                                campaign.campaign_objective,
                                "LEAD_GENERATION",
                            ),
                            "status": status,
                            "special_ad_categories": [],
                            "is_adset_budget_sharing_enabled": False,
                        },
                        "adset": {
                            "name": f"{campaign.campaign_name} FB AdSet",
                            "billing_event": "IMPRESSIONS",
                            "optimization_goal": "LINK_CLICKS",
                            "destination_type": "WEBSITE",
                            "daily_budget": fb_daily_budget,
                            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                            "targeting": {
                                "geo_locations": {
                                    "countries": [fb_country],
                                    "state": fb_state,
                                },
                                "publisher_platforms": ["facebook"],
                            },
                            "promoted_object": {"page_id": social_fb.page_id},
                            "status": status,
                        },
                        "ad": {
                            "name": f"{campaign.campaign_name} FB Ad",
                            "message": facebook_message,
                            "link": "http://lms-vidaisolutions.metavaratechnologies.com",
                            "image_url": campaign.image_url,
                        },
                    }

                    send_to_zapier_social(
                        facebook_payload
                    )

                # ===================================
                # INSTAGRAM
                # ===================================
                if "instagram" in channels:

                    social_ig = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="facebook",
                        is_active=True,
                    ).first()

                    if not social_ig:
                        return Response(
                            {"error": "Instagram/Facebook not connected"},
                            status=400,
                        )

                    if not social_ig.org_urn:
                        return Response(
                            {"error": "Instagram actor id missing"},
                            status=400,
                        )

                    status = (
                        "PAUSED"
                        if (campaign.status or "").lower() == "draft"
                        else "ACTIVE"
                    )

                    ig_budget = float(
                        filtered_budget.get("instagram", 2)
                    )

                    usd_to_inr = get_usd_to_inr()

                    ig_daily_budget = math.ceil(
                        (ig_budget * usd_to_inr) * 100
                    )

                    ig_platform_data = raw_platform_data.get(
                        "instagram",
                        {}
                    ) or {}

                    if isinstance(ig_platform_data, dict):
                        instagram_message = ig_platform_data.get(
                            "content",
                            ""
                        )

                        ig_country = ig_platform_data.get(
                            "country_code",
                            "IN"
                        )
                        ig_state = ig_platform_data.get("state")

                    else:
                        instagram_message = str(
                            ig_platform_data
                        )

                        ig_country = "IN"

                    instagram_payload = {
                        "event": "meta_ads_create",
                        "platform": "instagram",
                        "schedule_datetime": (
                            campaign.selected_start.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            if campaign.selected_start
                            else None
                        ),
                        "access_token": social_ig.access_token,
                        "ad_account_id": social_ig.account_id,
                        "page_id": social_ig.page_id,
                        "campaign": {
                            "internal_campaign_id": str(campaign.id),
                            "name": f"{campaign.campaign_name}",
                            "objective": CAMPAIGN_OBJECTIVES.get(
                                campaign.campaign_objective,
                                "OUTCOME_TRAFFIC",
                            ),
                            "status": status,
                            "special_ad_categories": [],
                            "is_adset_budget_sharing_enabled": False,
                        },
                        "adset": {
                            "name": f"{campaign.campaign_name} IG AdSet",
                            "billing_event": "IMPRESSIONS",
                            "optimization_goal": "LINK_CLICKS",
                            "destination_type": "WEBSITE",
                            "daily_budget": ig_daily_budget,
                            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                            "targeting": {
                                "geo_locations": {
                                    "countries": [ig_country],
                                    "state": ig_state,
                                },
                                "publisher_platforms": ["instagram"],
                            },
                            "promoted_object": {
                                "page_id": social_ig.page_id,
                                "instagram_actor_id": social_ig.org_urn,
                            },
                            "status": status,
                        },
                        "ad": {
                            "name": f"{campaign.campaign_name} IG Ad",
                            "message": instagram_message,
                            "link": "http://lms-vidaisolutions.metavaratechnologies.com",
                            "image_url": campaign.image_url,
                        },
                    }

                    send_to_zapier_social(
                        instagram_payload
                    )

                # ===================================
                # LINKEDIN
                # ===================================
                if "linkedin" in channels:

                    social_li = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="linkedin",
                        is_active=True,
                    ).first()

                    if (
                        not social_li
                        or not social_li.access_token
                    ):
                        return Response(
                            {
                                "error": (
                                    "LinkedIn not connected"
                                )
                            },
                            status=400,
                        )

                    if (
                        not social_li.account_id
                        or not social_li.org_urn
                        or not social_li.campaign_group
                    ):
                        return Response(
                            {
                                "error":(
                                  "LinkedIn account setup incomplete"
                                )
                            },
                            status=400,
                        )

                    linkedin_payload = (
                        LinkedInPayloadBuilder.create(
                            campaign=campaign,
                            social_account=social_li,
                            validated_data=data,
                        )
                    )

                    send_to_zapier_social(
                        linkedin_payload
                    )

                # ===================================
                # GOOGLE ADS
                # ===================================
                if "google_ads" in channels:

                    google_account = SocialAccount.objects.filter(
                        clinic_id=clinic_id,
                        platform="google",
                        is_active=True,
                    ).first()

                    refresh_token = (
                        google_account.user_token
                        if google_account
                        else None
                    )

                    access_token = (
                        google_account.access_token
                        if google_account
                        else None
                    )

                    customer_id = (
                        google_account.customer_id
                        if google_account
                        else None
                    )
                    login_customer_id = str(
                        getattr(google_account, "login_customer_id", None)
                        or getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
                    ).replace("-", "")

                    if not refresh_token:
                        refresh_token = getattr(
                            settings,
                            "GOOGLE_REFRESH_TOKEN",
                            None,
                        )

                    if not customer_id:
                        customer_id = getattr(
                            settings,
                            "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
                            None,
                        )

                    if refresh_token:
                        clinic_obj = Clinic.objects.filter(
                            id=clinic_id
                        ).first()

                        clinic_website = (
                            getattr(
                                clinic_obj,
                                "website",
                                None,
                            )
                            or getattr(
                                clinic_obj,
                                "clinic_url",
                                None,
                            )
                            or settings.BACKEND_BASE_URL
                        )

                        raw_google_data = (
                            campaign.platform_data.get(
                                "google_ads",
                                {},
                            )
                        )

                        if isinstance(
                            raw_google_data,
                            str,
                        ):
                            google_data = {}
                        else:
                            google_data = raw_google_data

                        keywords_raw = (
                            google_data.get(
                                "keywords",
                                [],
                            )
                        )

                        keywords_str = (
                            ",".join(
                                keywords_raw
                            )
                            if isinstance(
                                keywords_raw,
                                list,
                            )
                            else str(
                                keywords_raw
                            )
                        )

                        google_payload = {
                            "event": "google_ads_campaign_created",
                            # -----------------------------------
                            # Scheduler
                            # -----------------------------------
                            "schedule_datetime": (
                                campaign.selected_start.strftime("%Y-%m-%d %H:%M:%S")
                                if campaign.selected_start
                                else None
                            ),
                            # -----------------------------------
                            # Auth
                            # -----------------------------------
                            "customer_id": str(customer_id).replace("-", ""),
                            "login_customer_id": str(login_customer_id).replace(
                                "-", ""
                            ),
                            "refresh_token": refresh_token,
                            "access_token": access_token or "",
                            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                            "client_id": settings.GOOGLE_CLIENT_ID,
                            "client_secret": settings.GOOGLE_CLIENT_SECRET,
                            # -----------------------------------
                            # Campaign
                            # -----------------------------------
                            "internal_campaign_id": str(campaign.id),
                            "campaign_name": campaign.campaign_name,
                            "campaign_type": google_data.get(
                                "campaign_type",
                                "SEARCH",
                            ),
                            # -----------------------------------
                            # Status
                            # -----------------------------------
                            "campaign_status": (
                                "PAUSED"
                                if (campaign.status or "").lower() == "draft"
                                else "ENABLED"
                            ),
                            "our_status": (campaign.status or "").lower(),
                            # -----------------------------------
                            # Budget / Bidding
                            # -----------------------------------
                            "budget": int(
                                filtered_budget.get(
                                    "google_ads",
                                    500,
                                )
                            ),
                            "bidding_strategy": google_data.get(
                                "bidding_strategy",
                                "MANUAL_CPC",
                            ),
                            "cpc_bid": int(
                                google_data.get(
                                    "cpc_bid",
                                    2,
                                )
                            ),
                            # -----------------------------------
                            # Keywords
                            # -----------------------------------
                            "keywords": keywords_str,
                            # -----------------------------------
                            # URLs
                            # -----------------------------------
                            "final_url": clinic_website,
                            # ✅ NEVER NULL
                            "image_url": (campaign.image_url or DEFAULT_CAMPAIGN_IMAGE),
                            # -----------------------------------
                            # Headlines
                            # -----------------------------------
                            "headline_1": google_data.get(
                                "headline_1",
                                campaign.campaign_name[:30],
                            ),
                            "headline_2": google_data.get(
                                "headline_2",
                                "Learn More",
                            ),
                            "headline_3": google_data.get(
                                "headline_3",
                                "Contact Us Today",
                            ),
                            # -----------------------------------
                            # Descriptions
                            # -----------------------------------
                            "description": google_data.get(
                                "description",
                                strip_tags(
                                    campaign.campaign_description
                                    or campaign.campaign_name
                                )[:90],
                            ),
                            "description_2": google_data.get(
                                "description_2",
                                "Call us now or visit our website.",
                            )[:90],
                            # -----------------------------------
                            # Ad Group
                            # -----------------------------------
                            "ad_group_name": google_data.get(
                                "ad_group_name",
                                f"{campaign.campaign_name} AdGroup",
                            ),
                            # -----------------------------------
                            # Extra Metadata
                            # -----------------------------------
                            "campaign_objective": campaign.campaign_objective,
                            "target_audience": campaign.target_audience,
                            "start_date": str(campaign.start_date),
                            "end_date": str(campaign.end_date),
                            "start_time": (
                                campaign.enter_time.strftime("%H:%M")
                                if campaign.enter_time
                                else ""
                            ),
                            # -----------------------------------
                            # Callback
                            # -----------------------------------
                            "campaign_created_callback_url": (
                                f"{settings.BACKEND_BASE_URL}"
                                "/api/google-ads/callback/campaign-created/"
                            ),
                        }

                        try:
                            requests.post(
                                settings.ZAPIER_WEBHOOK_GOOGLE_ADS_URL,
                                json=google_payload,
                                headers={
                                    "Content-Type": "application/json",
                                    "login-customer-id": str(login_customer_id).replace(
                                        "-", ""
                                    ),
                                    "customer-id": str(customer_id).replace("-", ""),
                                },
                                timeout=10,
                            )

                            google_result = {
                                "status":"sent_to_zapier"
                            }
                        except Exception as e:
                            google_result = {
                                "status":"zapier_failed",
                                "error":str(e),
                            }

                created_campaigns.append(
                    {
                        "campaign_id": str(
                            campaign.id
                        ),
                        "mode": mode,
                        "platforms": channels,
                        "fb_post_id": fb_post_id,
                        "google_ads_status": (
                            google_result.get(
                                "status"
                            )
                            if "google_ads" in channels
                            else None
                        ),
                    }
                )

            return Response(
                {
                    "message": (
                      "Social media campaign(s) created successfully"
                    ),
                    "campaigns": created_campaigns,
                },
                status=201,
            )

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "trace": traceback.format_exc(),
                },
                status=400,
            )


class GoogleAdsCreateCampaignCallbackAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        internal_campaign_id = request.data.get("internal_campaign_id")

        try:

            campaign = Campaign.objects.get(id=internal_campaign_id)

            search_campaign_id = request.data.get("search_campaign_id")

            search_campaign_resource_name = request.data.get(
                "search_campaign_resource_name"
            )

            display_campaign_id = request.data.get("display_campaign_id")

            display_campaign_resource_name = request.data.get(
                "display_campaign_resource_name"
            )

            # -----------------------------------
            # platform_data
            # -----------------------------------

            platform_data = campaign.platform_data or {}

            google_data = platform_data.get("google_ads", {}) or {}

            google_data["search_campaign"] = {
                "campaign_id": search_campaign_id,
                "resource_name": search_campaign_resource_name,
            }

            google_data["display_campaign"] = {
                "campaign_id": display_campaign_id,
                "resource_name": display_campaign_resource_name,
            }

            platform_data["google_ads"] = google_data

            campaign.platform_data = platform_data

            # -----------------------------------
            # primary shortcut fields
            # -----------------------------------

            campaign.google_campaign_id = search_campaign_id

            campaign.google_campaign_resource_name = search_campaign_resource_name

            campaign.save(
                update_fields=[
                    "platform_data",
                    "google_campaign_id",
                    "google_campaign_resource_name",
                ]
            )

            return Response({"success": True})

        except Campaign.DoesNotExist:

            return Response(
                {"error": "Campaign not found"},
                status=404,
            )


class MetaCampaignCallbackAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        internal_campaign_id = request.data.get("internal_campaign_id")
        meta_campaign_id = request.data.get("meta_campaign_id")

        try:
            campaign = Campaign.objects.get(id=internal_campaign_id)

            platform = request.data.get("platform")

            if platform == "facebook":
                campaign.fb_campaign_id = meta_campaign_id

            elif platform == "instagram":
                campaign.instagram_campaign_id = meta_campaign_id
            campaign.save()

            return Response({"success": True})

        except Campaign.DoesNotExist:
            return Response({"error": "Campaign not found"}, status=404)


class FacebookCampaignStatusAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):

        try:
            action = request.data.get("action")

            if action not in ["enable", "disable"]:
                return Response(
                    {"error": "Invalid action"},
                    status=400,
                )

            campaign = Campaign.objects.get(id=campaign_id)
            platform = request.data.get("platform")

            meta_campaign_id = (
                campaign.fb_campaign_id
                if platform == "facebook"
                else campaign.instagram_campaign_id
            )

            if not meta_campaign_id:
                return Response(
                    {"error": "Facebook campaign not synced yet"},
                    status=400,
                )

            social_fb = SocialAccount.objects.filter(
                clinic=campaign.clinic,
                platform="facebook",
                is_active=True,
            ).first()

            if not social_fb:
                return Response(
                    {"error": "Facebook account not connected"},
                    status=400,
                )

            fb_status = "ACTIVE" if action == "enable" else "PAUSED"

            response = requests.post(
                f"https://graph.facebook.com/v25.0/{meta_campaign_id}",
                data={
                    "status": fb_status,
                    "access_token": social_fb.access_token,
                },
                timeout=15,
            )

            response_data = response.json()

            if response.status_code >= 400:
                return Response(
                    {
                        "error": "Facebook API error",
                        "details": response_data,
                    },
                    status=400,
                )

            return Response(
                {
                    "success": True,
                    "facebook_status": fb_status,
                    "response": response_data,
                }
            )

        except Campaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"},
                status=404,
            )

        except Exception as e:
            return Response(
                {
                    "error": str(e),
                    "trace": traceback.format_exc(),
                },
                status=400,
            )

# -------------------------------------------------------------------
# FACEBOOK CAMPAIGN UPDATE (Campaign + AdSet + Ad levels)
# PUT /api/fb/campaigns/<campaign_id>/update/
# -------------------------------------------------------------------
class FacebookCampaignUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            if not campaign.fb_campaign_id:
                return Response(
                    {"error": "Facebook campaign not synced yet"},
                    status=400,
                )

            social_fb = SocialAccount.objects.filter(
                clinic=campaign.clinic,
                platform="facebook",
                is_active=True,
            ).first()

            if not social_fb:
                return Response(
                    {"error": "Facebook account not connected"},
                    status=400,
                )

            data = request.data

            # ========== CAMPAIGN LEVEL UPDATES ==========
            campaign_updates = {}
            if "name" in data:
                campaign_updates["name"] = data["name"]
                campaign.campaign_name = data["name"]

            if "objective" in data:
                obj_map = {"awareness": "OUTCOME_AWARENESS", "leads": "OUTCOME_LEADS", "traffic": "OUTCOME_TRAFFIC"}
                fb_obj = obj_map.get(str(data["objective"]).lower(), "OUTCOME_TRAFFIC")
                campaign_updates["objective"] = fb_obj
                campaign.campaign_objective = data["objective"]

            if "status" in data:
                fb_status = "ACTIVE" if str(data["status"]).lower() == "live" else "PAUSED"
                campaign_updates["status"] = fb_status
                campaign.status = data["status"]

            # POST to Meta API - Campaign level
            if campaign_updates:
                resp = requests.post(
                    f"https://graph.facebook.com/v25.0/{campaign.fb_campaign_id}",
                    data={**campaign_updates, "access_token": social_fb.access_token},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    return Response({"error": "Facebook Campaign API error", "details": resp.json()}, status=400)

            # ========== ADSET LEVEL UPDATES ==========
            adset_updates = {}
            
            if "budget_data" in data:
                budget = data["budget_data"]
                if "facebook" in budget:
                    fb_budget = float(budget["facebook"])
                    usd_to_inr = get_usd_to_inr()
                    daily_budget_cents = math.ceil((fb_budget * usd_to_inr) * 100)
                    adset_updates["daily_budget"] = daily_budget_cents
                campaign.budget_data = data["budget_data"]

            if "platform_data" in data and "facebook" in data["platform_data"]:
                fb_data = data["platform_data"]["facebook"]
                if isinstance(fb_data, dict) and "targeting" in fb_data:
                    targeting = fb_data["targeting"]
                    adset_updates["targeting"] = {
                        "geo_locations": {"countries": targeting.get("countries", ["IN"])},
                        "publisher_platforms": ["facebook"],
                    }
                    if "state" in targeting:
                        adset_updates["targeting"]["geo_locations"]["state"] = targeting["state"]
                campaign.platform_data = data["platform_data"]

            # Get or fetch AdSet ID
            adset_id = (campaign.platform_data or {}).get("facebook", {}).get("adset_id")
            if not adset_id:
                camp_details = requests.get(
                    f"https://graph.facebook.com/v25.0/{campaign.fb_campaign_id}?fields=adsets",
                    params={"access_token": social_fb.access_token},
                    timeout=15,
                ).json()
                if camp_details.get("adsets", {}).get("data"):
                    adset_id = camp_details["adsets"]["data"][0]["id"]
                    if not campaign.platform_data:
                        campaign.platform_data = {}
                    if "facebook" not in campaign.platform_data:
                        campaign.platform_data["facebook"] = {}
                    campaign.platform_data["facebook"]["adset_id"] = adset_id

            # POST to Meta API - AdSet level
            if adset_updates and adset_id:
                resp = requests.post(
                    f"https://graph.facebook.com/v25.0/{adset_id}",
                    data={**adset_updates, "access_token": social_fb.access_token},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    return Response({"error": "Facebook AdSet API error", "details": resp.json()}, status=400)

            # ========== AD LEVEL UPDATES ==========
            ad_updates = {}
            if "campaign_content" in data:
                ad_updates["message"] = data["campaign_content"]
                campaign.campaign_content = data["campaign_content"]

            if "image_url" in data:
                ad_updates["image_url"] = data["image_url"]
                campaign.image_url = data["image_url"]

            # Get or fetch Ad ID
            ad_id = (campaign.platform_data or {}).get("facebook", {}).get("ad_id")
            if not ad_id and adset_id:
                adset_details = requests.get(
                    f"https://graph.facebook.com/v25.0/{adset_id}?fields=ads",
                    params={"access_token": social_fb.access_token},
                    timeout=15,
                ).json()
                if adset_details.get("ads", {}).get("data"):
                    ad_id = adset_details["ads"]["data"][0]["id"]
                    if "facebook" not in campaign.platform_data:
                        campaign.platform_data["facebook"] = {}
                    campaign.platform_data["facebook"]["ad_id"] = ad_id

            # POST to Meta API - Ad level
            if ad_updates and ad_id:
                resp = requests.post(
                    f"https://graph.facebook.com/v25.0/{ad_id}",
                    data={**ad_updates, "access_token": social_fb.access_token},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    return Response({"error": "Facebook Ad API error", "details": resp.json()}, status=400)

            campaign.save()

            return Response({
                "success": True,
                "message": "Facebook campaign updated successfully",
                "campaign_id": str(campaign.id),
            })

        except Campaign.DoesNotExist:
            return Response({"error": "Campaign not found"}, status=404)
        except Exception as e:
            logger.error(f"Facebook Campaign Update Error:\n{traceback.format_exc()}")
            return Response({"error": str(e), "trace": traceback.format_exc()}, status=400)

# -------------------------------------------------------------------
# INSTAGRAM CAMPAIGN UPDATE (Campaign + AdSet + Ad levels)
# PUT /api/instagram/campaigns/<campaign_id>/update/
# -------------------------------------------------------------------
class InstagramCampaignUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)

            if not campaign.instagram_campaign_id:
                return Response(
                    {"error": "Instagram campaign not synced yet"},
                    status=400,
                )

            social_ig = SocialAccount.objects.filter(
                clinic=campaign.clinic,
                platform="facebook",
                is_active=True,
            ).first()

            if not social_ig:
                return Response(
                    {"error": "Instagram account not connected"},
                    status=400,
                )

            data = request.data

            # ========== CAMPAIGN LEVEL UPDATES ==========
            campaign_updates = {}
            if "name" in data:
                campaign_updates["name"] = data["name"]
                campaign.campaign_name = data["name"]

            if "objective" in data:
                obj_map = {"awareness": "OUTCOME_AWARENESS", "leads": "OUTCOME_LEADS", "traffic": "OUTCOME_TRAFFIC"}
                ig_obj = obj_map.get(str(data["objective"]).lower(), "OUTCOME_TRAFFIC")
                campaign_updates["objective"] = ig_obj
                campaign.campaign_objective = data["objective"]

            if "status" in data:
                ig_status = "ACTIVE" if str(data["status"]).lower() == "live" else "PAUSED"
                campaign_updates["status"] = ig_status
                campaign.status = data["status"]

            # POST to Meta API - Campaign level
            if campaign_updates:
                resp = requests.post(
                    f"https://graph.facebook.com/v25.0/{campaign.instagram_campaign_id}",
                    data={**campaign_updates, "access_token": social_ig.access_token},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    return Response({"error": "Instagram Campaign API error", "details": resp.json()}, status=400)

            # ========== ADSET LEVEL UPDATES ==========
            adset_updates = {}
            
            if "budget_data" in data:
                budget = data["budget_data"]
                if "instagram" in budget:
                    ig_budget = float(budget["instagram"])
                    usd_to_inr = get_usd_to_inr()
                    daily_budget_cents = math.ceil((ig_budget * usd_to_inr) * 100)
                    adset_updates["daily_budget"] = daily_budget_cents
                campaign.budget_data = data["budget_data"]

            if "platform_data" in data and "instagram" in data["platform_data"]:
                ig_data = data["platform_data"]["instagram"]
                if isinstance(ig_data, dict) and "targeting" in ig_data:
                    targeting = ig_data["targeting"]
                    adset_updates["targeting"] = {
                        "geo_locations": {"countries": targeting.get("countries", ["IN"])},
                        "publisher_platforms": ["instagram"],
                    }
                    if "state" in targeting:
                        adset_updates["targeting"]["geo_locations"]["state"] = targeting["state"]
                campaign.platform_data = data["platform_data"]

            # Get or fetch AdSet ID
            adset_id = (campaign.platform_data or {}).get("instagram", {}).get("adset_id")
            if not adset_id:
                camp_details = requests.get(
                    f"https://graph.facebook.com/v25.0/{campaign.instagram_campaign_id}?fields=adsets",
                    params={"access_token": social_ig.access_token},
                    timeout=15,
                ).json()
                if camp_details.get("adsets", {}).get("data"):
                    adset_id = camp_details["adsets"]["data"][0]["id"]
                    if not campaign.platform_data:
                        campaign.platform_data = {}
                    if "instagram" not in campaign.platform_data:
                        campaign.platform_data["instagram"] = {}
                    campaign.platform_data["instagram"]["adset_id"] = adset_id

            # POST to Meta API - AdSet level
            if adset_updates and adset_id:
                resp = requests.post(
                    f"https://graph.facebook.com/v25.0/{adset_id}",
                    data={**adset_updates, "access_token": social_ig.access_token},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    return Response({"error": "Instagram AdSet API error", "details": resp.json()}, status=400)

            # ========== AD LEVEL UPDATES ==========
            ad_updates = {}
            if "campaign_content" in data:
                ad_updates["message"] = data["campaign_content"]
                campaign.campaign_content = data["campaign_content"]

            if "image_url" in data:
                ad_updates["image_url"] = data["image_url"]
                campaign.image_url = data["image_url"]

            # Get or fetch Ad ID
            ad_id = (campaign.platform_data or {}).get("instagram", {}).get("ad_id")
            if not ad_id and adset_id:
                adset_details = requests.get(
                    f"https://graph.facebook.com/v25.0/{adset_id}?fields=ads",
                    params={"access_token": social_ig.access_token},
                    timeout=15,
                ).json()
                if adset_details.get("ads", {}).get("data"):
                    ad_id = adset_details["ads"]["data"][0]["id"]
                    if "instagram" not in campaign.platform_data:
                        campaign.platform_data["instagram"] = {}
                    campaign.platform_data["instagram"]["ad_id"] = ad_id

            # POST to Meta API - Ad level
            if ad_updates and ad_id:
                resp = requests.post(
                    f"https://graph.facebook.com/v25.0/{ad_id}",
                    data={**ad_updates, "access_token": social_ig.access_token},
                    timeout=15,
                )
                if resp.status_code >= 400:
                    return Response({"error": "Instagram Ad API error", "details": resp.json()}, status=400)

            campaign.save()

            return Response({
                "success": True,
                "message": "Instagram campaign updated successfully",
                "campaign_id": str(campaign.id),
            })

        except Campaign.DoesNotExist:
            return Response({"error": "Campaign not found"}, status=404)
        except Exception as e:
            logger.error(f"Instagram Campaign Update Error:\n{traceback.format_exc()}")
            return Response({"error": str(e), "trace": traceback.format_exc()}, status=400)

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
