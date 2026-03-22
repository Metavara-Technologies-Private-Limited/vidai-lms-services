import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_to_zapier(data):
    """
    Send data to the default Zapier webhook.
    Used for: lead events, campaign events, social media campaigns, etc.
    Webhook: ZAPIER_WEBHOOK_URL
    """
    try:
        print("🔔 Sending to Zapier...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_URL)
        print("🔹 Payload:", data)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_URL,
            json=data,
            timeout=8
        )

        print("✅ Zapier Status Code:", response.status_code)
        print("✅ Zapier Response:", response.text)

        return response.status_code

    except requests.exceptions.RequestException as e:
        print("❌ Zapier error:", str(e))
        return None


def send_to_zapier_email(data):
    """
    Send email campaign data to the unified Mailchimp Zapier webhook.
    Used for: EmailCampaignCreateAPIView — event: "email_campaign_created"
    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL
    """
    try:
        print("🔔 Sending to Zapier (Email Campaign — Merged Mailchimp Zap)...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_MAILCHIMP_URL)
        print("🔹 Payload:", data)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_MAILCHIMP_URL,
            json=data,
            timeout=8
        )

        print("✅ Zapier Email Status Code:", response.status_code)
        print("✅ Zapier Email Response:", response.text)

        return response.status_code

    except requests.exceptions.RequestException as e:
        print("❌ Zapier Email error:", str(e))
        return None


def send_to_zapier_mailchimp_insights(data):
    """
    Send Mailchimp insights data to the unified Mailchimp Zapier webhook.
    Used for: CampaignMailchimpInsightsAPIView — event: "mailchimp_insights_requested"
    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL
    """
    try:
        print("🔔 Sending to Zapier (Mailchimp Insights — Merged Mailchimp Zap)...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_MAILCHIMP_URL)
        print("🔹 Payload:", data)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_MAILCHIMP_URL,
            json=data,
            timeout=8
        )

        print("✅ Zapier Insights Status Code:", response.status_code)
        print("✅ Zapier Insights Response:", response.text)

        return response.status_code

    except requests.exceptions.RequestException as e:
        print("❌ Zapier Insights error:", str(e))
        return None


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
    try:
        print("🔔 Sending to Zapier (SMS → MSG91)...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_SMS_URL)
        print("🔹 Payload:", payload)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_SMS_URL,
            json=payload,
            timeout=15,
        )

        print("✅ Zapier SMS Status Code:", response.status_code)
        print("✅ Zapier SMS Response:", response.text)

        logger.info(
            f"[Zapier SMS] Fired | to={payload.get('to')} "
            f"| lead={payload.get('lead_uuid')} "
            f"| status={response.status_code}"
        )

        return response

    except requests.exceptions.RequestException as e:
        print("❌ Zapier SMS error:", str(e))
        logger.warning(f"[Zapier SMS] Webhook failed: {e}")
        return None