"""
restapi/services/twilio_service.py

Twilio service layer — SMS, outbound calls, browser-based Voice SDK calls.

Required Django settings (set via environment variables):
─────────────────────────────────────────────────────────
  TWILIO_ACCOUNT_SID      ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN       your_auth_token          (used for SMS / REST calls)
  TWILIO_FROM_NUMBER      +1xxxxxxxxxx             (your Twilio phone number)

  # ── Browser / Voice SDK (needed for generate_browser_call_token) ──────────
  TWILIO_API_KEY          SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  ← CREATE in console
  TWILIO_API_SECRET       your_api_key_secret                ← shown ONCE on create
  TWILIO_TWIML_APP_SID    APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  ← TwiML App SID

  # ── Optional ──────────────────────────────────────────────────────────────
  TWILIO_DIRECT_CALL_RECORD   false   (set "true" to record browser calls)
  ZAPIER_WEBHOOK_URL          https://...  (leave blank to skip)
"""

import logging
import traceback
import requests

from django.conf import settings

logger = logging.getLogger(__name__)

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


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_twilio_client():
    """Return an authenticated Twilio REST client."""
    from twilio.rest import Client
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token  = getattr(settings, "TWILIO_AUTH_TOKEN", "")

    if not account_sid or not auth_token:
        raise ValueError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in Django settings."
        )

    return Client(account_sid, auth_token)


def _require_setting(name: str) -> str:
    """
    Read a required Django setting and raise a clear ValueError if missing/blank.
    This surfaces as a useful 500 message rather than a cryptic AttributeError.
    """
    value = getattr(settings, name, "")
    if not value:
        raise ValueError(
            f"Django setting '{name}' is missing or empty. "
            f"Set it in your .env / settings file and restart the server."
        )
    return value


# ─────────────────────────────────────────────────────────────────────────────
# SMS
# ─────────────────────────────────────────────────────────────────────────────

def send_sms(lead_uuid: str, to_number: str, message_body: str):
    """
    Send an SMS via Twilio REST API and persist a TwilioMessage record.
    Returns the saved TwilioMessage ORM object.
    """
    from restapi.models import Lead, TwilioMessage  # local import avoids circular

    client      = _get_twilio_client()
    from_number = _require_setting("TWILIO_FROM_NUMBER")

    message = client.messages.create(
        body=message_body,
        from_=from_number,
        to=to_number,
    )

    lead = Lead.objects.filter(id=lead_uuid).first()

    twilio_msg = TwilioMessage.objects.create(
        lead=lead,
        sid=message.sid,
        to_number=to_number,
        from_number=from_number,
        body=message_body,
        status=message.status,
        direction="outbound",
        raw_payload={},
    )

    logger.info("send_sms: sid=%s status=%s", message.sid, message.status)
    return twilio_msg


# ─────────────────────────────────────────────────────────────────────────────
# Outbound call (server-side REST, not browser SDK)
# ─────────────────────────────────────────────────────────────────────────────

def make_call(lead_uuid: str, to_number: str):
    """
    Initiate an outbound call via Twilio REST API and persist a TwilioCall record.
    Returns the saved TwilioCall ORM object.
    """
    from restapi.models import Lead, TwilioCall  # local import

    client      = _get_twilio_client()
    from_number = _require_setting("TWILIO_FROM_NUMBER")

    # Build a status-callback URL if configured
    callback_url = getattr(settings, "TWILIO_CALL_STATUS_CALLBACK_URL", "")
    call_kwargs = {
        "from_": from_number,
        "to": to_number,
        "twiml": "<Response><Say>Hello from Crysta Clinic. We will connect you shortly.</Say></Response>",
    }
    if callback_url:
        call_kwargs["status_callback"]        = callback_url
        call_kwargs["status_callback_method"] = "POST"

    call = client.calls.create(**call_kwargs)

    lead = Lead.objects.filter(id=lead_uuid).first()

    twilio_call = TwilioCall.objects.create(
        lead=lead,
        sid=call.sid,
        to_number=to_number,
        from_number=from_number,
        status=call.status,
        direction="outbound",
        raw_payload={},
    )

    logger.info("make_call: sid=%s status=%s", call.sid, call.status)
    return twilio_call


# ─────────────────────────────────────────────────────────────────────────────
# Browser / Voice SDK — Token generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_browser_call_token(identity: str) -> dict:
    """
    Generate a Twilio AccessToken that lets the browser Voice SDK make calls.

    Returns: { "token": "<jwt>", "identity": "<identity>" }

    Required settings
    -----------------
    TWILIO_ACCOUNT_SID    — AC...
    TWILIO_API_KEY        — SK...   (API Key SID,   NOT the Auth Token)
    TWILIO_API_SECRET     — ...     (API Key Secret, shown once on creation)
    TWILIO_TWIML_APP_SID  — AP...   (TwiML App SID)

    How to create these (one-time setup)
    -------------------------------------
    1. Twilio Console → Account → API keys & tokens → Create API key
       → copy SID (SK...) as TWILIO_API_KEY
       → copy Secret as TWILIO_API_SECRET  (shown only once!)

    2. Twilio Console → Voice → TwiML Apps → Create new TwiML App
       → set Voice Request URL to:
           https://<your-domain>/api/twilio/browser-call/twiml/
       → copy App SID (AP...) as TWILIO_TWIML_APP_SID
    """
    try:
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import VoiceGrant
    except ImportError:
        raise RuntimeError(
            "twilio package is not installed. Run: pip install twilio"
        )

    # ── Read required credentials ─────────────────────────────────────────
    account_sid    = _require_setting("TWILIO_ACCOUNT_SID")
    api_key        = _require_setting("TWILIO_API_KEY")          # SK...
    api_secret     = _require_setting("TWILIO_API_SECRET")
    twiml_app_sid  = _require_setting("TWILIO_TWIML_APP_SID")   # AP...

    logger.info(
        "generate_browser_call_token: identity=%s account_sid=%s api_key=%s twiml_app=%s",
        identity,
        account_sid[:8] + "...",
        api_key[:8] + "...",
        twiml_app_sid[:8] + "...",
    )

    # ── Build token ───────────────────────────────────────────────────────
    #
    # IMPORTANT: AccessToken takes (account_sid, api_key_sid, api_key_secret)
    #            NOT (account_sid, auth_token) — that's a common mistake.
    #
    token = AccessToken(
        account_sid,
        api_key,        # ← API Key SID (SK...)
        api_secret,     # ← API Key Secret
        identity=identity,
        ttl=3600,       # token valid for 1 hour
    )

    voice_grant = VoiceGrant(
        outgoing_application_sid=twiml_app_sid,
        incoming_allow=True,   # allows inbound calls to the browser too
    )
    token.add_grant(voice_grant)

    jwt = token.to_jwt().decode("utf-8")

    logger.info(
        "generate_browser_call_token: token generated for identity=%s",
        identity
    )

    return {
        "token": jwt,
        "identity": identity,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Browser call — TwiML webhook
# Called by Twilio when the browser SDK does Device.connect()
# ─────────────────────────────────────────────────────────────────────────────

def browser_call_twiml(to_number: str, record: bool = False) -> str:
    """
    Build TwiML that dials the patient's number when the browser SDK connects.

    Returns an XML string like:
        <Response>
          <Dial callerId="+1..." record="record-from-ringing">
            <Number>+919876543210</Number>
          </Dial>
        </Response>
    """
    try:
        from twilio.twiml.voice_response import VoiceResponse, Dial, Number
    except ImportError:
        raise RuntimeError("twilio package is not installed. Run: pip install twilio")

    from_number  = _require_setting("TWILIO_FROM_NUMBER")
    callback_url = getattr(settings, "TWILIO_CALL_STATUS_CALLBACK_URL", "")

    response = VoiceResponse()

    if not to_number:
        # No destination — just play a message
        response.say("No destination number provided.")
        return str(response)

    dial = Dial(
        caller_id=from_number,
        record="record-from-ringing" if record else "do-not-record",
        **({"action": callback_url} if callback_url else {}),
    )
    dial.number(to_number)
    response.append(dial)

    logger.info(
        "browser_call_twiml: to=%s from=%s record=%s",
        to_number,
        from_number,
        record,
    )

    return str(response)


# ─────────────────────────────────────────────────────────────────────────────
# Browser call — log to DB once frontend has a real CallSid
# ─────────────────────────────────────────────────────────────────────────────

def log_browser_call(
    lead_uuid: str,
    to_number: str,
    sid: str,
    status: str,
    agent_identity: str = "",
):
    """
    Persist a TwilioCall record for a browser-initiated call.
    Returns the TwilioCall instance, or None if the lead is not found.
    """
    from restapi.models import Lead, TwilioCall  # local import

    lead = Lead.objects.filter(id=lead_uuid).first()
    if not lead:
        logger.warning("log_browser_call: lead not found for uuid=%s", lead_uuid)
        return None

    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "browser")

    call_log = TwilioCall.objects.create(
        lead=lead,
        sid=sid,
        to_number=to_number,
        from_number=from_number,
        status=status,
        direction="outbound",
        raw_payload={
            "source": "browser_sdk",
            "agent_identity": agent_identity,
        },
    )

    logger.info(
        "log_browser_call: lead=%s sid=%s status=%s",
        lead_uuid,
        sid,
        status,
    )

    return call_log


# ─────────────────────────────────────────────────────────────────────────────
# Zapier webhook (optional)
# ─────────────────────────────────────────────────────────────────────────────

def notify_zapier_event(event_type: str, payload: dict) -> None:
    """
    Fire-and-forget POST to a Zapier catch-hook webhook.
    Set ZAPIER_WEBHOOK_URL in settings to enable; silently skipped if blank.
    """
    webhook_url = getattr(settings, "ZAPIER_WEBHOOK_URL", "")
    if not webhook_url:
        return

    try:
        resp = requests.post(
            webhook_url,
            json={"event": event_type, **payload},
            timeout=5,
        )
        logger.info(
            "notify_zapier_event: event=%s status=%s",
            event_type,
            resp.status_code,
        )
    except Exception:
        logger.warning(
            "notify_zapier_event: failed to POST to Zapier\n%s",
            traceback.format_exc(),
        )