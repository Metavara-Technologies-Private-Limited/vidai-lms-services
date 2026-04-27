import requests
import logging
import uuid

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Dial
from django.conf import settings

from restapi.models import TwilioMessage, TwilioCall
from restapi.models.lead import Lead


logger = logging.getLogger("restapi")


# ============================================================
# HELPERS
# ============================================================

def _format_phone(number: str, default_country_code: str = "+91") -> str:

    if not number:
        return ""

    raw = str(number).strip()
    raw = raw.replace(" ", "").replace("-", "")

    # preserve + if exists
    if raw.startswith("+"):
        digits = raw[1:]
    else:
        digits = "".join(ch for ch in raw if ch.isdigit())

    if not digits:
        return ""

    # Handle prefixes
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10:
        logger.error(f"Invalid phone length: {number}")
        return ""

    if digits[0] not in ["6", "7", "8", "9"]:
        logger.error(f"Invalid start digit: {number}")
        return ""

    if digits in ["0000000000", "1111111111", "1234567890"]:
        logger.error(f"Dummy phone number: {number}")
        return ""

    if len(set(digits)) == 1:
        logger.error(f"All digits same: {number}")
        return ""

    return f"{default_country_code}{digits}"


def _notify_zapier(event: str, payload: dict):
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
    _notify_zapier(event, payload)


def _build_call_twiml(agent_number: str = "") -> str:
    response = VoiceResponse()

    if agent_number:
        dial = Dial(callerId=settings.TWILIO_PHONE_NUMBER, answerOnBridge=True, timeout=30)
        dial.number(agent_number)
        response.append(dial)
        response.say("We could not connect your call right now. Please try again later.")
    else:
        response.say("Hello, this is a call from your clinic. We will be in touch with you shortly. Thank you.")

    return str(response)


# ============================================================
# SEND SMS
# ============================================================

def send_sms(lead_uuid, to_number, message_body):

    lead = Lead.objects.get(id=lead_uuid)
    clinic = getattr(lead, "clinic", None)  # ✅ ADDED

    formatted_to_number = _format_phone(to_number)
    if not formatted_to_number:
        raise Exception("Invalid phone number")

    lead_phone = _format_phone(lead.contact_no or formatted_to_number)
    sms_via_zapier = bool(getattr(settings, "TWILIO_SMS_VIA_ZAPIER", False))

    if sms_via_zapier:
        zap_sid = f"ZAP-SMS-{uuid.uuid4().hex}"
        zap_status = "queued_in_zapier"

        _notify_zapier("sms_sent", {
            "lead_uuid": str(lead_uuid),
            "lead_name": lead.full_name,
            "lead_email": lead.email or "",
            "lead_phone": lead_phone,
            "from_number": settings.TWILIO_PHONE_NUMBER,
            "to_number": formatted_to_number,
            "message_body": message_body,
            "sid": zap_sid,
            "status": zap_status,
        })
        logger.info(
            "SMS dispatched via Zapier: lead_uuid=%s sid=%s from=%s to=%s status=%s",
            lead_uuid,
            zap_sid,
            settings.TWILIO_PHONE_NUMBER,
            formatted_to_number,
            zap_status,
        )

        message_log = TwilioMessage.objects.create(
            lead=lead,
            clinic=clinic,  # ✅ ADDED
            sid=zap_sid,
            from_number=settings.TWILIO_PHONE_NUMBER,
            to_number=formatted_to_number,
            body=message_body,
            status=zap_status,
            direction="outbound",
            raw_payload={
                "sid": zap_sid,
                "status": zap_status,
                "source": "zapier",
            },
        )

        return message_log

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )
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
        clinic=clinic,  # ✅ ADDED
        sid=message.sid,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=formatted_to_number,
        body=message_body,
        status=message.status,
        direction="outbound",
        raw_payload={"sid": message.sid, "status": message.status}
    )
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

def make_call(lead_uuid, to_number, agent_number=None):

    lead = Lead.objects.get(id=lead_uuid)
    clinic = getattr(lead, "clinic", None)  # ✅ ADDED

    formatted_to_number = _format_phone(to_number)
    if not formatted_to_number:
        raise Exception("Invalid phone number")

    formatted_agent_number = _format_phone(agent_number or getattr(settings, "TWILIO_BRIDGE_NUMBER", ""))
    lead_phone = _format_phone(lead.contact_no or formatted_to_number)
    call_via_zapier = bool(getattr(settings, "TWILIO_CALL_VIA_ZAPIER", False))

    if call_via_zapier:
        zap_sid = f"ZAP-CALL-{uuid.uuid4().hex}"
        zap_status = "queued_in_zapier"
        _notify_zapier("call_initiated", {
            "lead_uuid": str(lead_uuid),
            "lead_name": lead.full_name,
            "lead_email": lead.email or "",
            "lead_phone": lead_phone,
            "from_number": settings.TWILIO_PHONE_NUMBER,
            "to_number": formatted_to_number,
            "agent_number": formatted_agent_number,
            "sid": zap_sid,
            "status": zap_status,
        })

        logger.info(
            "Call dispatched via Zapier: lead_uuid=%s sid=%s from=%s to=%s status=%s",
            lead_uuid,
            zap_sid,
            settings.TWILIO_PHONE_NUMBER,
            formatted_to_number,
            zap_status,
        )

        call_log = TwilioCall.objects.create(
            lead=lead,
            clinic=clinic,  # ✅ ADDED
            sid=zap_sid,
            from_number=settings.TWILIO_PHONE_NUMBER,
            to_number=formatted_to_number,
            status=zap_status,
            raw_payload={
                "sid": zap_sid,
                "status": zap_status,
                "agent_number": formatted_agent_number or None,
                "source": "zapier",
            },
        )

        return call_log

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    call_status_callback_url = getattr(settings, "TWILIO_CALL_STATUS_CALLBACK_URL", "").strip()

    call_kwargs = {
        "to": formatted_to_number,
        "from_": settings.TWILIO_PHONE_NUMBER,
        "twiml": _build_call_twiml(formatted_agent_number),
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
    if formatted_agent_number:
        logger.info("Twilio call bridge target configured: %s", formatted_agent_number)
    else:
        logger.info("Twilio call bridge target missing; using message-only TwiML fallback.")

    TwilioCall.objects.create(
        lead=lead,
        clinic=clinic,  # ✅ ADDED
        sid=call.sid,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=formatted_to_number,
        status=call.status,
        raw_payload={
            "sid": call.sid,
            "status": call.status,
            "agent_number": formatted_agent_number or None,
        }
    )
    _notify_zapier("call_initiated", {
        "lead_uuid" : str(lead_uuid),
        "lead_name" : lead.full_name,
        "lead_email": lead.email or "",
        "lead_phone": lead_phone,
        "from_number": settings.TWILIO_PHONE_NUMBER,
        "to_number" : formatted_to_number,
        "agent_number": formatted_agent_number,
        "sid"       : call.sid,
        "status"    : call.status,
    })


    return call