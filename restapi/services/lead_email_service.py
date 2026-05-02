import requests
import logging
from django.utils import timezone
from django.utils.html import strip_tags
from django.db import transaction
from django.shortcuts import get_object_or_404

from restapi.models import LeadEmail

logger = logging.getLogger(__name__)

# 🔥 YOUR ZAPIER WEBHOOK
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/27387148/uvl9my1/"


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

        # ✅ SEND TO ZAPIER INSTEAD OF SMTP
        payload = {
            "to_email": email_obj.lead.email,
            "subject": email_obj.subject,
            "message": body,
            "clinic_email": email_obj.clinic.email if email_obj.clinic else None,
            "sender_email": email_obj.sender_email
        }

        response = requests.post(
            ZAPIER_WEBHOOK_URL,
            json=payload,
            timeout=5
        )

        logger.info(f"Zapier Response: {response.status_code} - {response.text}")

        # ✅ SUCCESS
        if response.status_code == 200:
            email_obj.status = "SENT"
            email_obj.sent_at = timezone.now()
            email_obj.failed_reason = None
        else:
            email_obj.status = "FAILED"
            email_obj.failed_reason = f"Zapier Error {response.status_code}"

        email_obj.save(update_fields=["status", "sent_at", "failed_reason"])

        return email_obj

    except Exception as e:
        logger.error(f"Zapier Error: {str(e)}")

        email_obj.status = "FAILED"
        email_obj.failed_reason = str(e)
        email_obj.save(update_fields=["status", "failed_reason"])

        raise e