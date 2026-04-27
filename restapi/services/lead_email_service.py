import logging

from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404

from restapi.models import LeadEmail

logger = logging.getLogger(__name__)


@transaction.atomic
def send_lead_email(email_id):

    # 🔒 Lock row to prevent race condition
    email_obj = (
        LeadEmail.objects.select_for_update()
        .select_related("lead", "clinic")
        .get(id=email_id)
    )

    # ✅ Prevent duplicate sending
    if email_obj.status == LeadEmail.StatusChoices.SENT:
        raise Exception("Email already sent")

    # ✅ Ensure clinic exists
    if not email_obj.clinic:
        raise Exception("Clinic not assigned")

    # ✅ Validate lead email
    if not email_obj.lead or not email_obj.lead.email:
        raise Exception("Lead does not have a valid email address")

    # ✅ Validate sender email
    if not email_obj.sender_email:
        raise Exception("Sender email is required")

    try:
        send_mail(
            subject=email_obj.subject,
            message=email_obj.email_body,
            from_email=email_obj.sender_email,
            recipient_list=[email_obj.lead.email],
            fail_silently=False,
        )

        email_obj.status = LeadEmail.StatusChoices.SENT
        email_obj.sent_at = timezone.now()
        email_obj.failed_reason = None

        email_obj.save(update_fields=["status", "sent_at", "failed_reason"])

        logger.info(f"Email sent successfully: {email_obj.id}")

        return email_obj

    except Exception as e:
        email_obj.status = LeadEmail.StatusChoices.FAILED
        email_obj.failed_reason = str(e)

        email_obj.save(update_fields=["status", "failed_reason"])

        logger.error(f"Email sending failed: {email_obj.id} | Error: {str(e)}")

        raise e