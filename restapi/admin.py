from django.contrib import admin

from .models.campaign import Campaign
from .models.campaign_email_config import CampaignEmailConfig
from .models.campaign_social_media_config import CampaignSocialMediaConfig
from .models.lead import Lead


# -------------------------------------------------
# Register LMS Models
# -------------------------------------------------

admin.site.register(Campaign)
admin.site.register(CampaignEmailConfig)
admin.site.register(CampaignSocialMediaConfig)
admin.site.register(Lead)
