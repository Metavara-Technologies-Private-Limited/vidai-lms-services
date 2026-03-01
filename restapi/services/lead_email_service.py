from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404

from restapi.models import LeadEmail


@transaction.atomic
def send_lead_email(email_id):

    email_obj = get_object_or_404(LeadEmail, id=email_id)

    # ✅ Prevent resending
    if email_obj.status == "SENT":
        raise Exception("Email already sent")

    # ✅ Check lead email exists
    if not email_obj.lead.email:
        raise Exception("Lead does not have a valid email address")

    try:
        send_mail(
            subject=email_obj.subject,
            message=email_obj.email_body,
            from_email=email_obj.sender_email,
            recipient_list=[email_obj.lead.email],
            fail_silently=False,
        )

        email_obj.status = "SENT"
        email_obj.sent_at = timezone.now()
        email_obj.failed_reason = None
        email_obj.save(update_fields=["status", "sent_at", "failed_reason"])

        return email_obj

    except Exception as e:
        email_obj.status = "FAILED"
        email_obj.failed_reason = str(e)
        email_obj.save(update_fields=["status", "failed_reason"])

        raise e