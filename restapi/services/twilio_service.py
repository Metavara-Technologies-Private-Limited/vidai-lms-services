"""
restapi/services/twilio_service.py

Twilio service layer — SMS, outbound calls, browser-based Voice SDK calls,
and WhatsApp Business API (Meta Graph API + Twilio sender).

Required Django settings (set via environment variables):
─────────────────────────────────────────────────────────
  TWILIO_ACCOUNT_SID      ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN       your_auth_token          (used for SMS / REST calls)
  TWILIO_FROM_NUMBER      +1xxxxxxxxxx             (your Twilio phone number)

  # ── Browser / Voice SDK (needed for generate_browser_call_token) ──────────
  TWILIO_API_KEY          SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  ← CREATE in console
  TWILIO_API_SECRET       your_api_key_secret                ← shown ONCE on create
  TWILIO_TWIML_APP_SID    APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  ← TwiML App SID

  # ── WhatsApp ──────────────────────────────────────────────────────────────
  TWILIO_WHATSAPP_NUMBER  +15559532396             (your approved WA sender)
  META_ACCESS_TOKEN       EAAxxxxx...              (Meta System User token)
  META_WABA_ID            12795269375799024        (WhatsApp Business Account ID)

  # ── Optional ──────────────────────────────────────────────────────────────
  TWILIO_DIRECT_CALL_RECORD   false   (set "true" to record browser calls)
  ZAPIER_WEBHOOK_URL          https://...  (leave blank to skip)
  ZAPIER_WHATSAPP_WEBHOOK_URL https://...  (separate Zapier hook for WhatsApp)
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
        "machine_detection": "Enable",
    }
    if callback_url:
        call_kwargs["status_callback"]        = callback_url
        call_kwargs["status_callback_method"] = "POST"

        call_kwargs["status_callback_event"] = [
        "initiated",
        "ringing",
        "answered",
        "completed",
    ]
        

    call = client.calls.create(**call_kwargs)

    lead = Lead.objects.filter(id=lead_uuid).first()

    twilio_call = TwilioCall.objects.create(
        lead=lead,
        sid=call.sid,
        to_number=to_number,
        from_number=from_number,
        status=call.status,
        
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

    token_value = token.to_jwt()

    if isinstance(token_value, bytes):
       

       jwt = token_value.decode("utf-8")

    else:
       
      
      
       jwt = token_value

    logger.info("generate_browser_call_token: token generated for identity=%s",
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


# ═════════════════════════════════════════════════════════════════════════════


# WhatsApp Business API — Twilio sender
# Uses existing TemplateWhatsApp model (restapi_template_whatsapp table)
#
# FIELDS on TemplateWhatsApp:
#   id, clinic, name, use_case, body, created_by,
#   is_active, is_deleted, created_at, modified_at
#
# NOTE: TemplateWhatsApp has NO fields: body_text, language, status,
#       raw_payload, meta_template_id — these do NOT exist on the model.
#       The deleted WhatsAppTemplate had those; TemplateWhatsApp does NOT.
# ═════════════════════════════════════════════════════════════════════════════

META_GRAPH_VERSION = "v19.0"
META_GRAPH_BASE    = f"https://graph.facebook.com/{META_GRAPH_VERSION}"


def _meta_headers() -> dict:
    """Return Authorization header for Meta Graph API calls."""
    token = _require_setting("META_ACCESS_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


def _notify_zapier_whatsapp(event_type: str, payload: dict) -> None:
    """
    Fire-and-forget POST to the WhatsApp-specific Zapier hook.
    Falls back to the general ZAPIER_WEBHOOK_URL if the WA-specific one is blank.
    """
    webhook_url = (
        getattr(settings, "ZAPIER_WHATSAPP_WEBHOOK_URL", "")
        or getattr(settings, "ZAPIER_WEBHOOK_URL", "")
    )
    if not webhook_url:
        return

    try:
        resp = requests.post(
            webhook_url,
            json={"event": event_type, **payload},
            timeout=5,
        )
        logger.info(
            "_notify_zapier_whatsapp: event=%s status=%s",
            event_type,
            resp.status_code,
        )
    except Exception:
        logger.warning(
            "_notify_zapier_whatsapp: failed\n%s",
            traceback.format_exc(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL: build final message by substituting placeholders
# ─────────────────────────────────────────────────────────────────────────────

def _build_template_body(
    variable_values: list,
    template_id: str = None,
    template_name: str = "",
    template_body: str = None,
) -> str:
    """
    Substitute {{1}}, {{2}} … in template body with variable_values.

    Lookup priority:
      1. template_body  — if caller passed it directly (fastest, no DB hit)
      2. template_id    — UUID lookup in TemplateWhatsApp
      3. template_name  — name lookup in TemplateWhatsApp (fallback)

    Returns the substituted string, or joined variable_values as last resort.
    """
    from restapi.models.template_whatsapp import TemplateWhatsApp   # ✅ FIXED

    body = template_body  # may be None

    if not body and template_id:
        tmpl = TemplateWhatsApp.objects.filter(
            id=template_id,
            is_active=True,
            is_deleted=False,
        ).first()
        if tmpl:
            body = tmpl.body   # ← correct field name

    if not body and template_name:
        tmpl = TemplateWhatsApp.objects.filter(
            name=template_name,
            is_active=True,
            is_deleted=False,
        ).first()
        if tmpl:
            body = tmpl.body   # ← correct field name

    if not body:
        logger.warning(
            "_build_template_body: template not found (id=%s name=%s), "
            "falling back to raw variable values",
            template_id, template_name,
        )
        return " ".join(str(v) for v in variable_values)

    for i, val in enumerate(variable_values, start=1):
        body = body.replace(f"{{{{{i}}}}}", str(val))

    return body


# ─────────────────────────────────────────────────────────────────────────────
# SEND — single WhatsApp message
# ─────────────────────────────────────────────────────────────────────────────

def send_whatsapp_message(
    lead_uuid:       str,
    to_number:       str,
    template_name:   str,
    language:        str,
    variable_values: list,
    clinic_id:       int  = None,
    template_id:     str  = None,
    template_body:   str  = None,
):
    """
    Send an approved WhatsApp template message via Twilio.

    Parameters
    ----------
    lead_uuid       : UUID of the Lead (can be "" for bulk sends)
    to_number       : recipient E.164 number e.g. "+919876543210"
    template_name   : name of the TemplateWhatsApp record (for snapshot)
    language        : stored in WhatsAppMessage snapshot only
    variable_values : list of values for {{1}}, {{2}} ... placeholders
    clinic_id       : optional clinic FK id
    template_id     : UUID of TemplateWhatsApp in DB (preferred)
    template_body   : pre-fetched body string (skips DB lookup if provided)

    Returns the saved WhatsAppMessage ORM object.
    Fires Zapier event: whatsapp_message_sent
    """
    from restapi.models                   import WhatsAppMessage
    from restapi.models.lead              import Lead
    from restapi.models.clinic            import Clinic
    from restapi.models.template_whatsapp import TemplateWhatsApp   # ✅ FIXED

    client         = _get_twilio_client()
    wa_from_number = _require_setting("TWILIO_WHATSAPP_NUMBER")

    from_wa = f"whatsapp:{wa_from_number}"
    to_wa   = f"whatsapp:{to_number}"

    # ── Build final message body ──────────────────────────────────────────
    final_body = _build_template_body(
        variable_values = variable_values,
        template_id     = template_id,
        template_name   = template_name,
        template_body   = template_body,
    )

    # ── Send via Twilio ───────────────────────────────────────────────────
    message = client.messages.create(
        from_ = from_wa,
        to    = to_wa,
        body  = final_body,
    )

    logger.info(
        "send_whatsapp_message: sid=%s to=%s template=%s status=%s",
        message.sid, to_number, template_name, message.status,
    )

    # ── Resolve FK objects ────────────────────────────────────────────────
    lead   = Lead.objects.filter(id=lead_uuid).first() if lead_uuid else None
    clinic = None
    if clinic_id:
        clinic = Clinic.objects.filter(id=clinic_id).first()
    elif lead:
        clinic = getattr(lead, "clinic", None)

    # Prefer UUID lookup; fall back to name
    if template_id:
        template = TemplateWhatsApp.objects.filter(id=template_id).first()
    else:
        template = TemplateWhatsApp.objects.filter(name=template_name).first()

    # ── Persist to DB ─────────────────────────────────────────────────────
    wa_msg = WhatsAppMessage.objects.create(
        lead            = lead,
        clinic          = clinic,
        template        = template,
        sid             = message.sid,
        to_number       = to_number,
        from_number     = wa_from_number,
        template_name   = template_name,
        language        = language,
        variable_values = variable_values,
        status          = message.status,
        raw_payload     = {
            "sid":      message.sid,
            "status":   message.status,
            "to":       to_wa,
            "from":     from_wa,
            "template": template_name,
        },
    )

    # ── Zapier ────────────────────────────────────────────────────────────
    _notify_zapier_whatsapp("whatsapp_message_sent", {
        "sid":           message.sid,
        "to_number":     to_number,
        "template_name": template_name,
        "language":      language,
        "status":        message.status,
        "lead_uuid":     str(lead_uuid) if lead_uuid else None,
        "clinic_id":     clinic_id,
        "template_id":   template_id,
    })

    return wa_msg


# ─────────────────────────────────────────────────────────────────────────────
# BULK SEND — same template to multiple numbers
# ─────────────────────────────────────────────────────────────────────────────

def bulk_send_whatsapp(
    recipients:    list,
    template_name: str,
    language:      str,
    clinic_id:     int  = None,
    template_id:   str  = None,
    template_body: str  = None,
) -> list:
    """
    Send the same WhatsApp template to multiple recipients.

    Each recipient dict must contain:
      to_number       (str, E.164)
      variable_values (list, optional)
      lead_uuid       (str, optional)

    Returns list of result dicts — one per recipient.
    Fires Zapier event: whatsapp_bulk_sent
    """
    results = []

    for r in recipients:
        to_number       = r.get("to_number", "")
        lead_uuid       = r.get("lead_uuid", "")
        variable_values = r.get("variable_values", [])

        try:
            wa_msg = send_whatsapp_message(
                lead_uuid       = lead_uuid,
                to_number       = to_number,
                template_name   = template_name,
                language        = language,
                variable_values = variable_values,
                clinic_id       = clinic_id,
                template_id     = template_id,
                template_body   = template_body,
            )
            results.append({
                "to_number": to_number,
                "status":    wa_msg.status,
                "sid":       wa_msg.sid,
            })
        except Exception as exc:
            logger.error(
                "bulk_send_whatsapp: failed for %s — %s", to_number, exc
            )
            results.append({
                "to_number": to_number,
                "status":    "error",
                "error":     str(exc),
            })

    logger.info(
        "bulk_send_whatsapp: template=%s total=%d",
        template_name, len(recipients),
    )

    _notify_zapier_whatsapp("whatsapp_bulk_sent", {
        "template_name": template_name,
        "template_id":   template_id,
        "total":         len(recipients),
        "success":       sum(1 for r in results if r.get("status") != "error"),
        "failed":        sum(1 for r in results if r.get("status") == "error"),
        "clinic_id":     clinic_id,
    })

    return results 