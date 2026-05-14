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

                selected_start = (
                    timezone.make_aware(
                        datetime.combine(
                            (
                                start
                                if isinstance(
                                    start,
                                    date_type,
                                )
                                else datetime.strptime(
                                    start,
                                    "%Y-%m-%d",
                                ).date()
                            ),
                            time(0,0,0),
                        )
                    )
                )

                selected_end = (
                    timezone.make_aware(
                        datetime.combine(
                            (
                                end
                                if isinstance(
                                    end,
                                    date_type,
                                )
                                else datetime.strptime(
                                    end,
                                    "%Y-%m-%d",
                                ).date()
                            ),
                            time(23,59,59),
                        )
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
                # Create campaign
                # -----------------------------------
                campaign = Campaign.objects.create(
                    clinic_id=data[
                        "clinic"
                    ],
                    campaign_name=data[
                        "campaign_name"
                    ],
                    campaign_description=data[
                        "campaign_description"
                    ],
                    campaign_objective=data[
                        "campaign_objective"
                    ],
                    target_audience=data[
                        "target_audience"
                    ],
                    start_date=data[
                        "start_date"
                    ],
                    end_date=data[
                        "end_date"
                    ],
                    campaign_mode=mode_mapping.get(
                        mode
                    ),
                    campaign_content=facebook_message,
                    selected_start=selected_start,
                    selected_end=selected_end,
                    enter_time=data[
                        "enter_time"
                    ],
                    platform_data=raw_platform_data,
                    budget_data=filtered_budget,
                    image_url=image_url_field,
                    status=data["status"],
                    is_active=True,
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

                    else:
                        facebook_message = str(
                            fb_platform_data
                        )

                        fb_country = "IN"

                    facebook_payload = {
                        "event": "meta_ads_create",
                        "platform": "facebook",
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
                                "geo_locations": {"countries":  [fb_country]},
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

                    else:
                        instagram_message = str(
                            ig_platform_data
                        )

                        ig_country = "IN"

                    instagram_payload = {
                        "event": "meta_ads_create",
                        "platform": "instagram",
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
                                "geo_locations": {"countries": [ig_country]},
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
                            "message": facebook_message,
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
                            "event":"google_ads_campaign_created",
                            "campaign_name": campaign.campaign_name,
                            "customer_id": str(customer_id).replace("-", ""),
                            "refresh_token": refresh_token,
                            "access_token": access_token or "",
                            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                            "client_id": settings.GOOGLE_CLIENT_ID,
                            "client_secret": settings.GOOGLE_CLIENT_SECRET,
                            "budget": int(
                                filtered_budget.get(
                                    "google_ads",
                                    500,
                                )
                            ),
                            "keywords": keywords_str,
                            "final_url": clinic_website,
                            "headline_1": campaign.campaign_name[:30],
                            "headline_2": "Book Free Consultation",
                            "headline_3": "Contact Us Today",
                            "description": strip_tags(
                                campaign.campaign_description
                                or campaign.campaign_name
                            )[:90],
                            "campaign_id": str(
                                campaign.id
                            ),
                            "callback_url": (
                                f"{settings.BACKEND_BASE_URL}/api/campaign/insights/callback/"
                            ),
                        }

                        try:
                            requests.post(
                                settings.ZAPIER_WEBHOOK_GOOGLE_ADS_URL,
                                json=google_payload,
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


class MetaCampaignCallbackAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        internal_campaign_id = request.data.get("internal_campaign_id")
        meta_campaign_id = request.data.get("meta_campaign_id")

        try:
            campaign = Campaign.objects.get(id=internal_campaign_id)

            campaign.fb_campaign_id = meta_campaign_id
            campaign.save()

            return Response({"success": True})

        except Campaign.DoesNotExist:
            return Response({"error": "Campaign not found"}, status=404)

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
