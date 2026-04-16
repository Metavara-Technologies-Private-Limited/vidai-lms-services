import logging
import requests

from django.conf import settings

logger = logging.getLogger("restapi")


def _safe_text(value, limit=250):
    """Limit response text in logs to avoid noisy terminal output."""
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _post_to_webhook(label: str, webhook_url: str, payload: dict, timeout: int):
    """Send payload to a Zapier webhook and log request/response details."""
    if not webhook_url:
        logger.warning("[%s] Webhook URL is not configured. Skipping request.", label)
        return None

    try:
        logger.info("[%s] Sending webhook | url=%s | payload=%s", label, webhook_url, payload)
        response = requests.post(webhook_url, json=payload, timeout=timeout)
        logger.info(
            "[%s] Response | status_code=%s | body=%s",
            label,
            response.status_code,
            _safe_text(response.text),
        )
        if not response.ok:
            logger.warning("[%s] Non-2xx response from Zapier: %s", label, response.status_code)
        return response
    except requests.exceptions.RequestException:
        logger.exception("[%s] Zapier request failed", label)
        return None


def send_to_zapier(data):
    """
    Send data to the default Zapier webhook.
    Used for: lead events, campaign events, social media campaigns, etc.
    Webhook: ZAPIER_WEBHOOK_URL
    """
    response = _post_to_webhook(
        label="Zapier General",
        webhook_url=getattr(settings, "ZAPIER_WEBHOOK_URL", ""),
        payload=data,
        timeout=8,
    )
    return response.status_code if response else None


def send_to_zapier_email(data):
    """
    Send email campaign data to the unified Mailchimp Zapier webhook.
    Used for: EmailCampaignCreateAPIView — event: "email_campaign_created"
    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL
    """
    response = _post_to_webhook(
        label="Zapier Mailchimp Email",
        webhook_url=getattr(settings, "ZAPIER_WEBHOOK_MAILCHIMP_URL", ""),
        payload=data,
        timeout=8,
    )
    return response.status_code if response else None


def send_to_zapier_reputation_email(data):
    """
    Send reputation review-request emails to the dedicated Zapier webhook.
    """
    response = _post_to_webhook(
        label="Zapier Reputation Email",
        webhook_url=(
            getattr(settings, "ZAPIER_WEBHOOK_REPUTATION_EMAIL_URL", "")
            or "https://hooks.zapier.com/hooks/catch/25767405/u771d3l/"
        ),
        payload=data,
        timeout=8,
    )
    return response.status_code if response else None


def send_to_zapier_social(data):
    """
    Send email campaign data to the unified Mailchimp Zapier webhook.
    Used for: EmailCampaignCreateAPIView — event: "email_campaign_created"
    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL
    """
    response = _post_to_webhook(
        label="Zapier Social",
        webhook_url=getattr(settings, "ZAPIER_WEBHOOK_SOCIAL_URL", ""),
        payload=data,
        timeout=8,
    )
    return response.status_code if response else None


def send_to_zapier_mailchimp_insights(data):
    """
    Send Mailchimp insights data to the unified Mailchimp Zapier webhook.
    Used for: CampaignMailchimpInsightsAPIView — event: "mailchimp_insights_requested"
    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL
    """
    response = _post_to_webhook(
        label="Zapier Mailchimp Insights",
        webhook_url=getattr(settings, "ZAPIER_WEBHOOK_MAILCHIMP_URL", ""),
        payload=data,
        timeout=8,
    )
    return response.status_code if response else None


# ─────────────────────────────────────────────────────────────────────────────
# SMS via Zapier → MSG91
# Django fires this → Zapier receives → Zapier calls MSG91 → SMS delivered
# ─────────────────────────────────────────────────────────────────────────────
def send_to_zapier_sms(payload: dict):
    """
    Fires Zapier SMS webhook.
    Zapier Zap: Catch Hook → MSG91 Send SMS

    Payload sent to Zapier:
        {
            "event":      "sms_requested",
            "lead_uuid":  "<uuid>",
            "lead_name":  "John Doe",
            "to":         "+91xxxxxxxxxx",
            "message":    "Hello from clinic!",
            "sender_id":  "MVTAPP",
            "clinic_id":  1
        }
    """
    response = _post_to_webhook(
        label="Zapier SMS",
        webhook_url=getattr(settings, "ZAPIER_WEBHOOK_SMS_URL", ""),
        payload=payload,
        timeout=15,
    )

    if response is not None:
        logger.info(
            "[Zapier SMS] Fired | to=%s | lead=%s | status=%s",
            payload.get("to"),
            payload.get("lead_uuid"),
            response.status_code,
        )

    return response
