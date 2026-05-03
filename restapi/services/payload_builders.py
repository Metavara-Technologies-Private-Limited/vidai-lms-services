from django.conf import settings


DEFAULT_LINKEDIN_CONFIG = {
    "geo_urn": "urn:li:geo:102713980",
    "bid_strategy": "MAX_DELIVERY",
    "optimization_goal": "LEAD_GENERATION",
    "bid_amount": None,
}


LINKEDIN_LOCATION_MAP = {
    "india": "urn:li:geo:102713980",
    "united states": "urn:li:geo:103644278",
    "usa": "urn:li:geo:103644278",
    "us": "urn:li:geo:103644278",
    "california": "urn:li:geo:102095887",
    "new york": "urn:li:geo:105080838",
    "texas": "urn:li:geo:104898711",
    "canada": "urn:li:geo:101174742",
    "united kingdom": "urn:li:geo:101165590",
    "uk": "urn:li:geo:101165590",
    "uae": "urn:li:geo:104305776",
    "australia": "urn:li:geo:101452733",
    "germany": "urn:li:geo:101282230",
    "singapore": "urn:li:geo:102454443",
}


class LinkedInPayloadBuilder:

    @staticmethod
    def get_callback_url():
        """
        Use separate callback base URL for Zapier callbacks.
        Falls back to BACKEND_BASE_URL if not configured.
        """

        callback_base = getattr(
            settings,
            "LINKEDIN_CALLBACK_BASE_URL",
            settings.BACKEND_BASE_URL
        )

        print("Using LinkedIn callback base URL:", callback_base)

        return (
            f"{callback_base}"
            "/api/webhooks/linkedin-zapier-callback/"
        )

    @staticmethod
    def resolve_geo_urn(linkedin_data):
        """
        Supports BOTH:
        1. geo_urn directly from frontend
        2. location text like 'India' or 'LA California'
        """

        # If frontend directly sends geo urn
        if linkedin_data.get("geo_urn"):
            return linkedin_data["geo_urn"]

        # If frontend sends readable location name
        location_name = (
            linkedin_data.get("location", "")
            .strip()
            .lower()
        )

        if not location_name:
            return DEFAULT_LINKEDIN_CONFIG["geo_urn"]

        # Exact match first
        if location_name in LINKEDIN_LOCATION_MAP:
            return LINKEDIN_LOCATION_MAP[location_name]

        # Partial match — e.g. "LA califronia" contains "california"
        for key, urn in LINKEDIN_LOCATION_MAP.items():
            if key in location_name:
                return urn

        # No match found — return default
        return DEFAULT_LINKEDIN_CONFIG["geo_urn"]

    # =========================================
    # STATUS
    # =========================================
    @staticmethod
    def status(campaign, social_account):
        return {
            "platform": "linkedin",
            "action": "STATUS",
            "internal_campaign_uuid": str(campaign.id),

            "callback_url":
                LinkedInPayloadBuilder.get_callback_url(),

            "auth": {
                "access_token": social_account.access_token,
                "account_id": social_account.account_id
            },

            "campaign": {
                "linkedin_campaign_id":
                    campaign.linkedin_external_campaign_id
            }
        }

    # =========================================
    # CREATE
    # =========================================
    @staticmethod
    def create(campaign, social_account, validated_data):

        # ✅ FIX: Read from campaign.platform_data (already saved to DB)
        # NOT from validated_data — serializer can lose nested dict fields
        raw_linkedin = campaign.platform_data.get("linkedin", {})

        if isinstance(raw_linkedin, dict):
            linkedin_data = raw_linkedin
        else:
            # Old string format fallback
            linkedin_data = {"content": str(raw_linkedin)}

        budget = (
            validated_data
            .get("budget_data", {})
            .get("linkedin", 280)
        )

        geo_urn = LinkedInPayloadBuilder.resolve_geo_urn(
            linkedin_data
        )

        return {
            "platform": "linkedin",
            "action": "CREATE",
            "event": "campaign_created",
            "internal_campaign_uuid": str(campaign.id),

            "callback_url":
                LinkedInPayloadBuilder.get_callback_url(),

            "auth": {
                "access_token": social_account.access_token,
                "account_id": social_account.account_id,
                "organization_urn": social_account.org_urn,
                "campaign_group_urn": social_account.campaign_group,
            },

            "campaign": {
                "internal_campaign_id": str(campaign.id),
                "name": campaign.campaign_name,
                "description": campaign.campaign_description,
                "status": campaign.status,
                "objective": campaign.campaign_objective,
                "target_audience": campaign.target_audience,

                "start_date_ms": int(
                    campaign.selected_start.timestamp() * 1000
                ) if campaign.selected_start else None,

                "budget": {
                    "amount": budget,
                    "type": "DAILY"
                },

                "bidding": {
                    "strategy": linkedin_data.get(
                        "bid_strategy",
                        DEFAULT_LINKEDIN_CONFIG["bid_strategy"]
                    ),
                    # ✅ FIX: bid_amount now correctly read from saved platform_data
                    "bid_amount": linkedin_data.get(
                        "bid_amount",
                        DEFAULT_LINKEDIN_CONFIG["bid_amount"]
                    )
                },

                "optimization": {
                    "goal": linkedin_data.get(
                        "optimization_goal",
                        DEFAULT_LINKEDIN_CONFIG["optimization_goal"]
                    )
                },

                "targeting": {
                    # ✅ FIX: location now correctly resolved from saved platform_data
                    "locations": [geo_urn],
                    "location_text": linkedin_data.get("location", ""),
                    "audience": campaign.target_audience,
                },

                "creative": {
                    "headline": linkedin_data.get(
                        "headline_1",
                        campaign.campaign_name[:70]
                    ),
                    # ✅ FIX: Use linkedin-specific content, fall back to campaign content
                    "message": linkedin_data.get(
                        "content",
                        campaign.campaign_content
                    ),
                    "destination_url": linkedin_data.get(
                        "final_url",
                        "https://yourclinic.com"
                    ),
                    "image_url": campaign.image_url,
                },

                "tracking": {
                    "conversion_enabled": True
                }
            }
        }

    # =========================================
    # UPDATE
    # =========================================
    @staticmethod
    def update(
        campaign,
        social_account,
        desired_status
    ):
        return {
            "platform": "linkedin",
            "action": "UPDATE",
            "event": "campaign_updated",

            "internal_campaign_uuid": str(campaign.id),

            "callback_url":
                LinkedInPayloadBuilder.get_callback_url(),

            "auth": {
                "access_token":
                    social_account.access_token,

                "account_id":
                    social_account.account_id,
            },

            "campaign": {
                "linkedin_campaign_id":
                    campaign.linkedin_external_campaign_id,

                "linkedin_campaign_urn":
                    campaign.linkedin_campaign_urn,

                "current_status":
                    campaign.linkedin_live_status,

                "desired_status":
                    desired_status,

                "name":
                    campaign.campaign_name,

                "budget": {
                    "amount":
                        campaign.budget_data.get(
                            "linkedin",
                            280
                        )
                }
            }
        }

    # =========================================
    # INSIGHTS
    # =========================================
    @staticmethod
    def insights(campaign, social_account):
        return {
            "platform": "linkedin",
            "action": "INSIGHTS",
            "event": "campaign_insights",

            "internal_campaign_uuid":
                str(campaign.id),

            "callback_url":
                LinkedInPayloadBuilder.get_callback_url(),

            "auth": {
                "access_token":
                    social_account.access_token,

                "account_id": str(
                    campaign.linkedin_account_id
                    or social_account.account_id
                ),
            },

            "campaign": {
                "linkedin_campaign_id":
                    campaign.linkedin_external_campaign_id,

                "linkedin_campaign_urn":
                    campaign.linkedin_campaign_urn,

                "creative_id":
                    campaign.linkedin_creative_id,

                "start_date":
                    str(campaign.start_date)
            }
        }