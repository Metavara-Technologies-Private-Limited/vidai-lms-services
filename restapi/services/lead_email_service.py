from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import strip_tags
from django.db import transaction
from django.shortcuts import get_object_or_404

from restapi.models import LeadEmail


def _clean_email_body(text):
    if not text:
        return ""

    import re

    decoded = (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
    )

    plain = strip_tags(decoded)
    plain = re.sub(r"\n{3,}", "\n\n", plain)

    return plain.strip()


@transaction.atomic
def send_lead_email(email_id):

    email_obj = get_object_or_404(LeadEmail, id=email_id)

    if email_obj.status == "SENT":
        raise Exception("Email already sent")

    if not email_obj.lead or not email_obj.lead.email:
        raise Exception("Lead email missing")

    if not email_obj.sender_email:
        raise Exception("Sender email missing")

    try:
        body = _clean_email_body(email_obj.email_body)

        send_mail(
            subject=email_obj.subject,
            message=body,
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