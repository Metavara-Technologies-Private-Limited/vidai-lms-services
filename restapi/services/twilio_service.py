import requests
import logging

from twilio.rest import Client
from django.conf import settings

from restapi.models import TwilioMessage, TwilioCall
from restapi.models.lead import Lead


logger = logging.getLogger("restapi")


# ============================================================
# HELPERS
# ============================================================

def _format_phone(number: str, default_country_code: str = "+91") -> str:
    """
    Normalize a phone number to E.164-like format.
    Examples:
    - 9108583181 -> +919108583181
    - +919108583181 -> +919108583181
    - 00919108583181 -> +919108583181
    """
    if not number:
        return ""

    raw = str(number).strip()
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == "+")

    # Convert 00 prefix into + (common international format).
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    if cleaned.startswith("+"):
        digits_after_plus = "".join(ch for ch in cleaned[1:] if ch.isdigit())
        return f"+{digits_after_plus}" if digits_after_plus else ""

    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if not digits:
        return ""

    country_digits = default_country_code.lstrip("+") if default_country_code else ""
    if len(digits) == 10 and country_digits:
        return f"+{country_digits}{digits}"

    # If caller already included country code but without +, just add +.
    if country_digits and digits.startswith(country_digits):
        return f"+{digits}"

    return f"+{digits}"


def _notify_zapier(event: str, payload: dict):
    """
    Fire a POST to the Zapier webhook so Zapier can
    trigger follow-up automations (email / SMS / sheets etc.)
    Safe — never raises; logs on failure.
    """
    url = getattr(settings, "ZAPIER_WEBHOOK_TWILIO_URL", None)
    if not url:
        logger.warning("ZAPIER_WEBHOOK_TWILIO_URL not set — skipping Zapier notify.")
        return
    try:
        response = requests.post(url, json={"event": event, **payload}, timeout=5)
        logger.info(
            "Zapier notified: event=%s status_code=%s",
            event,
            response.status_code,
        )
        if not response.ok:
            logger.warning(
                "Zapier webhook non-2xx response: event=%s status_code=%s body=%s",
                event,
                response.status_code,
                (response.text or "")[:200],
            )
    except Exception as e:
        logger.error(f"Zapier notify failed [{event}]: {e}")


def notify_zapier_event(event: str, payload: dict):
    """Public wrapper used by views/callback handlers to forward events to Zapier."""
    _notify_zapier(event, payload)


# ============================================================
# SEND SMS
# ============================================================

def send_sms(lead_uuid, to_number, message_body):

    lead = Lead.objects.get(id=lead_uuid)

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    formatted_to_number = _format_phone(to_number)
    sms_status_callback_url = getattr(settings, "TWILIO_SMS_STATUS_CALLBACK_URL", "").strip()

    sms_kwargs = {
        "body": message_body,
        "from_": settings.TWILIO_PHONE_NUMBER,
        "to": formatted_to_number,
    }
    if sms_status_callback_url:
        sms_kwargs["status_callback"] = sms_status_callback_url

    message = client.messages.create(**sms_kwargs)
    if sms_status_callback_url:
        logger.info("Twilio SMS status callback configured: %s", sms_status_callback_url)
    logger.info(
        "Twilio SMS sent: lead_uuid=%s sid=%s from=%s to=%s status=%s",
        lead_uuid,
        message.sid,
        settings.TWILIO_PHONE_NUMBER,
        formatted_to_number,
        message.status,
    )

    TwilioMessage.objects.create(
        lead=lead,
        sid=message.sid,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=formatted_to_number,
        body=message_body,
        status=message.status,
        direction="outbound",
        raw_payload={"sid": message.sid, "status": message.status}
    )

    lead_phone = _format_phone(lead.contact_no or formatted_to_number)

    _notify_zapier("sms_sent", {
        "lead_uuid"   : str(lead_uuid),
        "lead_name"   : lead.full_name,
        "lead_email"  : lead.email or "",
        "lead_phone"  : lead_phone,
        "from_number" : settings.TWILIO_PHONE_NUMBER,
        "to_number"   : formatted_to_number,
        "message_body": message_body,
        "sid"         : message.sid,
        "status"      : message.status,
    })

    return message


# ============================================================
# MAKE CALL
# ============================================================

def make_call(lead_uuid, to_number):

    lead = Lead.objects.get(id=lead_uuid)

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    formatted_to_number = _format_phone(to_number)
    call_status_callback_url = getattr(settings, "TWILIO_CALL_STATUS_CALLBACK_URL", "").strip()

    call_kwargs = {
        "to": formatted_to_number,
        "from_": settings.TWILIO_PHONE_NUMBER,
        "twiml": '<Response><Say>Hello, this is a call from your clinic. We will be in touch with you shortly. Thank you.</Say></Response>',
    }
    if call_status_callback_url:
        call_kwargs["status_callback"] = call_status_callback_url
        call_kwargs["status_callback_method"] = "POST"
        call_kwargs["status_callback_event"] = ["initiated", "ringing", "answered", "completed"]

    call = client.calls.create(**call_kwargs)
    if call_status_callback_url:
        logger.info("Twilio Call status callback configured: %s", call_status_callback_url)
    logger.info(
        "Twilio call initiated: lead_uuid=%s sid=%s from=%s to=%s status=%s",
        lead_uuid,
        call.sid,
        settings.TWILIO_PHONE_NUMBER,
        formatted_to_number,
        call.status,
    )

    TwilioCall.objects.create(
        lead=lead,
        sid=call.sid,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=formatted_to_number,
        status=call.status,
        raw_payload={"sid": call.sid, "status": call.status}
    )

    lead_phone = _format_phone(lead.contact_no or formatted_to_number)

    _notify_zapier("call_initiated", {
        "lead_uuid" : str(lead_uuid),
        "lead_name" : lead.full_name,
        "lead_email": lead.email or "",
        "lead_phone": lead_phone,
        "from_number": settings.TWILIO_PHONE_NUMBER,
        "to_number" : formatted_to_number,
        "sid"       : call.sid,
        "status"    : call.status,
    })

    return call