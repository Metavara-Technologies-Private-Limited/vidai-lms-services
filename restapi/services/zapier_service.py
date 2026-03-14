import requests
from django.conf import settings


def send_to_zapier(data):
    """
    Send data to the default Zapier webhook.
    Used for: lead events, campaign events, social media campaigns, etc.
    Webhook: ZAPIER_WEBHOOK_URL  (unchanged — same as before)
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

    Previously used ZAPIER_WEBHOOK_EMAIL_URL (separate Zap — now deleted).
    Now uses ZAPIER_WEBHOOK_MAILCHIMP_URL — the single merged Mailchimp Zap.
    The Zap routes this to Path A based on event = "email_campaign_created".

    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL
    """
    try:
        print("🔔 Sending to Zapier (Email Campaign — Merged Mailchimp Zap)...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_MAILCHIMP_URL)
        print("🔹 Payload:", data)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_MAILCHIMP_URL,  # ✅ merged Mailchimp Zap
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

    Previously used ZAPIER_WEBHOOK_MAILCHIMP_INSIGHTS_URL (separate Zap — now deleted).
    Now uses ZAPIER_WEBHOOK_MAILCHIMP_URL — the single merged Mailchimp Zap.
    The Zap routes this to Path B based on event = "mailchimp_insights_requested".

    Webhook: ZAPIER_WEBHOOK_MAILCHIMP_URL

    Payload shape (all fields are pre-computed by the view before calling this):
        {
            "event":                  "mailchimp_insights_requested",
            "campaign_id":            "<uuid>",
            "mailchimp_campaign_id":  "<mailchimp-id>",
            "campaign_name":          "...",
            "emails_sent":            6,
            "opens":                  3,
            "open_rate":              50.0,
            "clicks":                 1,
            "click_rate":             16.7,
            "bounces":                0,
            "unsubscribes":           0,
            "last_open":              "2026-03-10T07:18:00",
            "last_click":             "2026-03-10T07:20:00",
        }
    """
    try:
        print("🔔 Sending to Zapier (Mailchimp Insights — Merged Mailchimp Zap)...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_MAILCHIMP_URL)
        print("🔹 Payload:", data)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_MAILCHIMP_URL,  # ✅ merged Mailchimp Zap
            json=data,
            timeout=8
        )

        print("✅ Zapier Insights Status Code:", response.status_code)
        print("✅ Zapier Insights Response:", response.text)

        return response.status_code

    except requests.exceptions.RequestException as e:
        print("❌ Zapier Insights error:", str(e))
        return None