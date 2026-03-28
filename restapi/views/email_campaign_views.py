# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Campaign, CampaignEmailConfig, Lead
from restapi.serializers.campaign_serializer import EmailCampaignCreateSerializer

from restapi.services.mailchimp_service import (
    sync_contacts_to_mailchimp,
    create_and_send_mailchimp_campaign,
)
from restapi.services.zapier_service import send_to_zapier_email

logger = logging.getLogger(__name__)

CAMPAIGN_OBJECTIVES = {
    "awareness": "Brand Awareness",
    "leads": "Lead Generation",
}

class EmailCampaignCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Create Email Campaign Only",
        request_body=EmailCampaignCreateSerializer,
        responses={
            201: "Email Campaign Created Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Email Campaign"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            serializer = EmailCampaignCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            selected_start = data.get("selected_start")
            enter_time = data.get("enter_time")

            now = timezone.now()

            scheduled_datetime = None

            if not selected_start or not enter_time:
                campaign_status = "draft"
                is_active_value = False
            else:
                scheduled_datetime = timezone.make_aware(
                    datetime.combine(selected_start, enter_time)
                )

                if scheduled_datetime > now:
                    campaign_status = "scheduled"
                    is_active_value = True
                else:
                    campaign_status = "live"
                    is_active_value = True

            campaign = Campaign.objects.create(
                clinic_id=data["clinic"],
                campaign_name=data["campaign_name"],
                campaign_description=data["campaign_description"],
                campaign_objective=data["campaign_objective"],
                target_audience=data["target_audience"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                campaign_mode=Campaign.EMAIL,
                selected_start=data.get("selected_start"),
                selected_end=data.get("selected_end"),
                enter_time=data.get("enter_time"),
                status=campaign_status,
                is_active=is_active_value,
            )

            emails = list(
                Lead.objects.filter(clinic=campaign.clinic, email__isnull=False)
                .exclude(email="")
                .values_list("email", flat=True)
            )

            created_email_configs = []

            for email_data in data["email"]:
                email_config = CampaignEmailConfig.objects.create(
                    campaign=campaign,
                    audience_name=email_data["audience_name"],
                    subject=email_data["subject"],
                    email_body=email_data["email_body"],
                    template_name=email_data.get("template_name"),
                    sender_email=email_data["sender_email"],
                    scheduled_at=scheduled_datetime,
                    is_active=True,
                )

                sync_contacts_to_mailchimp(emails)

                mailchimp_id = create_and_send_mailchimp_campaign(
                    campaign_id=str(campaign.id),
                    subject=email_config.subject,
                    email_body=email_config.email_body,
                    sender_email=email_config.sender_email,
                    campaign_name=campaign.campaign_name,
                    scheduled_at=scheduled_datetime,
                )

                # 3. Save mailchimp_campaign_id on campaign for later metric fetching
                campaign.mailchimp_campaign_id = mailchimp_id
                campaign.save(update_fields=["mailchimp_campaign_id"])

                # ---------------------------------------------------------
                # FUTURE: Fetch template attachments and send file URLs
                # ---------------------------------------------------------
                attachments = []

                # Uncomment later when template attachments are enabled
                # try:
                #     from restapi.models import TemplateMailDocument  # adjust import
                #
                #     template_docs = TemplateMailDocument.objects.filter(
                #         template__name=email_config.template_name
                #     )
                #
                #     for doc in template_docs:
                #         attachments.append({
                #             "file_url": request.build_absolute_uri(doc.file.url),
                #             "file_name": doc.file.name.split("/")[-1],
                #         })
                #
                # except Exception:
                #     logger.warning("Failed to fetch template attachments")
                # ---------------------------------------------------------

                # ── Send email campaign data to dedicated Email Zapier webhook ──
                # Uses send_to_zapier_email → ZAPIER_WEBHOOK_EMAIL_URL
                # (NOT the generic ZAPIER_WEBHOOK_URL used for leads/social campaigns)
                send_to_zapier_email(
                    {
                        "event": "email_campaign_created",
                        "emails": emails,
                        "campaign_id": str(campaign.id),
                        "campaign_name": campaign.campaign_name,
                        "campaign_description": campaign.campaign_description,
                        "campaign_objective": CAMPAIGN_OBJECTIVES.get(
                            campaign.campaign_objective
                        ),
                        "target_audience": campaign.target_audience,
                        "start_date": campaign.start_date.isoformat(),
                        "end_date": campaign.end_date.isoformat(),
                        "subject": email_config.subject,
                        "email_body": email_config.email_body,
                        "sender_email": email_config.sender_email,
                        "scheduled_at": (
                            email_config.scheduled_at.isoformat()
                            if email_config.scheduled_at
                            else None
                        ),
                        # "attachments": attachments
                    }
                )

                created_email_configs.append(
                    {
                        "email_config_id": email_config.id,
                        "audience_name": email_config.audience_name,
                    }
                )

            return Response(
                {
                    "message": "Email campaign created successfully",
                    "campaign_id": campaign.id,
                    "emails": created_email_configs,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Email Campaign Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )