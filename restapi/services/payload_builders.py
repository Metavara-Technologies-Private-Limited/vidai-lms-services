DEFAULT_LINKEDIN_CONFIG = {
    "geo_urn": "urn:li:geo:102713980",
    "bid_strategy": "MAX_DELIVERY",
    "optimization_goal": "LEAD_GENERATION",
    "bid_amount": None,
}


class LinkedInPayloadBuilder:
    
    
    
    @staticmethod
    def status(campaign, social_account):
        return {
        "platform":"linkedin",
        "action":"STATUS",

        "internal_campaign_uuid":
            str(campaign.id),

        "callback_url": "https://winter-foundationary-shockingly.ngrok-free.dev/api/webhooks/linkedin-zapier-callback/",

        "auth":{
            "access_token":
                social_account.access_token,
            "account_id":
                social_account.account_id
        },

        "campaign":{
            "linkedin_campaign_id":
                campaign.linkedin_external_campaign_id
        }
        }

    @staticmethod
    def create(campaign, social_account, validated_data):

        linkedin_data = (
            validated_data
            .get("platform_data", {})
            .get("linkedin", {})
        )

        budget = (
            validated_data
            .get("budget_data", {})
            .get("linkedin", 280)
        )

        return {
            "platform": "linkedin",
            "action": "CREATE",
            "event": "campaign_created",
            "internal_campaign_uuid": str(campaign.id),
            "callback_url": "https://winter-foundationary-shockingly.ngrok-free.dev/api/webhooks/linkedin-zapier-callback/",


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
                "status": "PAUSED",

                "objective": campaign.campaign_objective,
                "target_audience": campaign.target_audience,

                "start_date_ms": int(
                    campaign.selected_start.timestamp()*1000
                ) if campaign.selected_start else None,

                "budget": {
                    "amount": budget,
                    "type": "DAILY"
                },

                "bidding": {
                    "strategy": DEFAULT_LINKEDIN_CONFIG["bid_strategy"],
                    "bid_amount": DEFAULT_LINKEDIN_CONFIG["bid_amount"]
                },

                "optimization": {
                    "goal": DEFAULT_LINKEDIN_CONFIG[
                        "optimization_goal"
                    ]
                },

                "targeting": {
                    "locations": [
                        DEFAULT_LINKEDIN_CONFIG["geo_urn"]
                    ],
                    "audience": campaign.target_audience,
                },

                "creative": {
                    "headline": linkedin_data.get(
                        "headline_1",
                        campaign.campaign_name[:70]
                    ),
                    "message": campaign.campaign_content,
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


    @staticmethod
    def update(
        campaign,
        social_account,
        desired_status
    ):

        return {
            "platform":"linkedin",
            "action":"UPDATE",
            "event":"campaign_updated",

            "internal_campaign_uuid":
                str(campaign.id),

            "callback_url":
            "https://winter-foundationary-shockingly.ngrok-free.dev/api/webhooks/linkedin-zapier-callback/",

            "auth":{
                "access_token":
                    social_account.access_token,

                "account_id":
                    social_account.account_id,
            },

            "campaign":{

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

                "budget":{
                    "amount":
                        campaign.budget_data.get(
                            "linkedin",
                            280
                        )
                }
            }
        }


    @staticmethod
    def insights(campaign, social_account):

        return {
            "platform":"linkedin",
            "action":"INSIGHTS",
            "event":"campaign_insights",

            "internal_campaign_uuid": str(
                campaign.id
            ),
            
            "callback_url":
    "https://winter-foundationary-shockingly.ngrok-free.dev/api/webhooks/linkedin-zapier-callback/",


            "auth":{
                "access_token": social_account.access_token,
                "account_id": str(
                    campaign.linkedin_account_id
                    or social_account.account_id
                ),
            },

            "campaign":{
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