# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from datetime import datetime, time

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

            campaign_status = data.get("status")

            if campaign_status == "draft":
                scheduled_datetime = None
                is_active_value = False

            elif campaign_status == "scheduled":
                if not selected_start or not enter_time:
                    raise ValidationError("Scheduled campaigns require date and time")

                scheduled_datetime = timezone.make_aware(
                    datetime.combine(selected_start, enter_time)
                )
                is_active_value = True

            elif campaign_status == "live":
                scheduled_datetime = now
                is_active_value = True

            else:
                raise ValidationError("Invalid campaign status")

            selected_start_date = data.get("selected_start")
            selected_end_date = data.get("selected_end")

            selected_start_dt = None
            selected_end_dt = None

            if selected_start_date:
                selected_start_dt = timezone.make_aware(
                    datetime.combine(selected_start_date, time.min)
                )

            if selected_end_date:
                selected_end_dt = timezone.make_aware(
                    datetime.combine(selected_end_date, time.min)
                )

            campaign = Campaign.objects.create(
                clinic_id=data["clinic"],
                campaign_name=data["campaign_name"],
                campaign_description=data["campaign_description"],
                campaign_objective=data["campaign_objective"],
                target_audience=data["target_audience"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                campaign_mode=Campaign.EMAIL,
                selected_start=selected_start_dt,
                selected_end=selected_end_dt,
                enter_time=data.get("enter_time"),
                status=campaign_status,
                is_active=is_active_value,
            )

            queryset = Lead.objects.filter(
                clinic=campaign.clinic,
                email__isnull=False
            ).exclude(email="")

            # All Audience -> Exclude Converted
            queryset = queryset.exclude(lead_status="converted")

            # Active Audience -> Exclude Lost
            if data.get("target_audience") == "active":
                queryset = queryset.exclude(lead_status__in=["lost", "lost lead"])

            emailsTest = sorted(
                set(
                    email.strip().lower()
                    for email in queryset.values_list("email", flat=True)
                    if email
                )
            )
            # Temporarily sending mails to self account
            print("Emails: ")
            print(emailsTest)
            emails = "sohan.m.14911@gmail.com"
            # Need to comment above and uncomment below:
            # emails = emailsTest

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

                send_to_zapier_email(
                    {
                        "event": "email_campaign_created",
                        "status": campaign_status,
                        "emails": emails,
                        "campaign_id": str(campaign.id),
                        "campaign_name": data.get("campaign_name"),
                        "campaign_description": data.get("campaign_description"),
                        "campaign_objective": CAMPAIGN_OBJECTIVES.get(
                            data.get("campaign_objective")
                        ),
                        "target_audience": data.get("target_audience"),
                        "start_date": (
                            data.get("start_date").isoformat()
                            if data.get("start_date")
                            else None
                        ),
                        "end_date": (
                            data.get("end_date").isoformat()
                            if data.get("end_date")
                            else None
                        ),
                        # Email fields (from loop email_data)
                        "subject": email_data.get("subject"),
                        "email_body": email_data.get("email_body"),
                        "sender_email": email_data.get("sender_email"),
                        # Schedule
                        "scheduled_at": (
                            scheduled_datetime.isoformat()
                            if scheduled_datetime
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

        except Exception as e:
            logger.error(str(e))
            logger.error(traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EmailSaveMailchimpCampaignIdAPIView(APIView):
    def post(self, request):
        campaign_id = request.data.get("campaign_id")
        mailchimp_id = request.data.get("mailchimp_campaign_id")

        if not campaign_id or not mailchimp_id:
            return Response({"error": "Missing fields"}, status=400)

        # Get latest email config for this campaign
        email_config = (
            CampaignEmailConfig.objects.filter(campaign_id=campaign_id)
            .order_by("-created_at")
            .first()
        )

        if not email_config:
            return Response({"error": "No email config found"}, status=400)

        # Update Mailchimp ID
        email_config.mailchimp_campaign_id = mailchimp_id
        email_config.save(update_fields=["mailchimp_campaign_id"])

        return Response({"status": "saved"})
