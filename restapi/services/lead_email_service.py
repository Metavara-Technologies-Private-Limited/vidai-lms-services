from datetime import timedelta
import re
from datetime import datetime
from uuid import uuid4
from django.utils.timezone import make_aware
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

def extract_time_range(body):
    match = re.search(r"Time:\s*(\d{1,2}:\d{2}\s*[APM]{2})\s*-\s*(\d{1,2}:\d{2}\s*[APM]{2})", body)
    
    if not match:
        return None, None

    start_str, end_str = match.groups()

    start_time = datetime.strptime(start_str, "%I:%M %p").time()
    end_time = datetime.strptime(end_str, "%I:%M %p").time()

    return start_time, end_time

def extract_date(body):
    match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", body)

    if not match:
        return None

    return datetime.strptime(match.group(1), "%Y-%m-%d").date()


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
        start_time_obj, end_time_obj = extract_time_range(body)

        date_obj = extract_date(body)

        if start_time_obj and date_obj:
            start_dt = make_aware(datetime.combine(date_obj, start_time_obj))
            end_dt = make_aware(datetime.combine(date_obj, end_time_obj))
        else:
            start_dt = email_obj.scheduled_at or timezone.now()
            end_dt = start_dt + timedelta(minutes=30)

        # ✅ SEND TO ZAPIER INSTEAD OF SMTP
        payload = {
            "to_email": email_obj.lead.email,
            "subject": email_obj.subject,
            "message": body,
            "clinic_email": email_obj.clinic.email if email_obj.clinic else None,
            "sender_email": email_obj.sender_email,
            "description": body,
        }

        has_appointment = bool(start_time_obj and end_time_obj and date_obj)

        # Only add calendar data if appointment exists
        if has_appointment:
            payload.update({
                "create_calendar_event": True,
                "create_google_meet": True,
                "event_title": email_obj.subject,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "timezone": "Asia/Kolkata",
                "attendees": [email_obj.lead.email],
                "location": (
                    email_obj.clinic.name if email_obj.clinic else "Online Consultation"
                ),
                # Include explicit conference creation hints for Zapier/Google Calendar.
                "conference_data_version": 1,
                "conference_data": {
                    "createRequest": {
                        "requestId": str(uuid4()),
                        "conferenceSolutionKey": {
                            "type": "hangoutsMeet"
                        },
                    }
                },
            })
        else:
            payload["create_calendar_event"] = False

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
