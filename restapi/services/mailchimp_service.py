import mailchimp_marketing as MailchimpClient
from mailchimp_marketing.api_client import ApiClientError
from django.conf import settings
from django.db import transaction
from restapi.models import MarketingEvent
import logging
import hashlib

logger = logging.getLogger(__name__)


def get_mailchimp_client():
    client = MailchimpClient.Client()
    client.set_config(
        {
            "api_key": settings.MAILCHIMP_API_KEY,
            "server": settings.MAILCHIMP_SERVER,
        }
    )
    return client


def get_subscriber_hash(email):
    """Mailchimp uses MD5 hash of lowercase email to identify subscribers."""
    return hashlib.md5(email.lower().encode()).hexdigest()


def sync_contacts_to_mailchimp(emails: list[str]):
    """
    Add/update a list of emails to Mailchimp audience.
    Deduplicates emails before sending to avoid Mailchimp duplicate error.
    """
    client = get_mailchimp_client()

    # ← Deduplicate: lowercase + unique only
    unique_emails = list({email.lower().strip() for email in emails if email})

    if not unique_emails:
        logger.warning("sync_contacts_to_mailchimp called with empty email list")
        return None

    members = [
        {
            "email_address": email,
            "status_if_new": "subscribed",
            "status": "subscribed",
        }
        for email in unique_emails
    ]

    try:
        response = client.lists.batch_list_members(
            settings.MAILCHIMP_AUDIENCE_ID,
            {"members": members, "update_existing": True},
        )
        logger.info(
            f"Mailchimp sync: {response.get('total_created')} created, "
            f"{response.get('total_updated')} updated, "
            f"{response.get('error_count')} errors"
        )
        # Log any per-member errors (won't crash the whole batch)
        for err in response.get("errors", []):
            logger.warning(f"Mailchimp member error: {err}")
        return response
    except ApiClientError as e:
        logger.error(f"Mailchimp batch sync failed: {e.text}")
        raise


def create_and_send_mailchimp_campaign(
    campaign_id: str,
    subject: str,
    email_body: str,
    sender_email: str,
    campaign_name: str,
    scheduled_at=None,
):
    client = get_mailchimp_client()

    try:
        # Step 1: Create campaign
        campaign = client.campaigns.create(
            {
                "type": "regular",
                "recipients": {
                    "list_id": settings.MAILCHIMP_AUDIENCE_ID,
                },
                "settings": {
                    "subject_line": subject,
                    "from_name": campaign_name,
                    "reply_to": settings.MAILCHIMP_SENDER_EMAIL,
                    "title": campaign_name,
                },
                "tracking": {
                    "opens": True,
                    "html_clicks": True,
                    "text_clicks": True,
                },
            }
        )

        mailchimp_campaign_id = campaign["id"]
        logger.info(f"Mailchimp campaign created: {mailchimp_campaign_id}")

        # Step 2: Set email content
        client.campaigns.set_content(mailchimp_campaign_id, {"html": email_body})

        # Step 3: Send immediately
        # NOTE: Scheduling requires Mailchimp paid plan (Standard+)
        client.campaigns.send(mailchimp_campaign_id)
        logger.info(f"Mailchimp campaign sent: {mailchimp_campaign_id}")

        return mailchimp_campaign_id

    except ApiClientError as e:
        logger.error(f"Mailchimp campaign create/send failed: {e.text}")
        raise


def get_mailchimp_campaign_report(mailchimp_campaign_id: str):
    """
    Fetch full campaign report from Mailchimp.

    Returns:
        emails_sent     — total emails sent
        opens           — unique opens count
        open_rate       — open rate percentage (e.g. 45.5)
        clicks          — unique clicks count
        click_rate      — click rate percentage (e.g. 12.3)
        bounces         — hard + soft bounce count
        unsubscribes    — unsubscribe count
        last_open       — datetime of last open (or None)
        last_click      — datetime of last click (or None)
    """
    client = get_mailchimp_client()

    try:
        report = client.reports.get_campaign_report(mailchimp_campaign_id)

        # ── Bounces ───────────────────────────────────────────────────────
        bounces      = report.get("bounces", {})
        hard_bounces = bounces.get("hard", {})
        soft_bounces = bounces.get("soft", {})

        # ── Opens ─────────────────────────────────────────────────────────
        opens_data   = report.get("opens", {})
        unique_opens = opens_data.get("unique_opens", 0)
        open_rate    = round(opens_data.get("open_rate", 0) * 100, 2)   # convert 0.45 → 45.0
        last_open    = opens_data.get("last_open", None)

        # ── Clicks ────────────────────────────────────────────────────────
        clicks_data   = report.get("clicks", {})
        unique_clicks = clicks_data.get("unique_clicks", 0)
        click_rate    = round(clicks_data.get("click_rate", 0) * 100, 2)  # convert 0.12 → 12.0
        last_click    = clicks_data.get("last_click", None)

        return {
            "emails_sent":   report.get("emails_sent", 0),
            "opens":         unique_opens,
            "open_rate":     open_rate,       # e.g. 45.5 means 45.5%
            "clicks":        unique_clicks,
            "click_rate":    click_rate,      # e.g. 12.3 means 12.3%
            "bounces":       (
                hard_bounces.get("bounce_count", 0)
                + soft_bounces.get("bounce_count", 0)
            ),
            "unsubscribes":  report.get("unsubscribed", 0),
            "last_open":     last_open,       # e.g. "2026-03-10T07:18:00+00:00"
            "last_click":    last_click,      # e.g. "2026-03-10T07:20:00+00:00"
        }

    except ApiClientError as e:
        logger.error(f"Mailchimp report fetch failed: {e.text}")
        return None


@transaction.atomic
def create_mailchimp_event(validated_data):
    """Store incoming Mailchimp webhook events."""
    event = MarketingEvent.objects.create(
        source=validated_data["source"],
        event_type=validated_data["event_type"],
        payload=validated_data["payload"],
    )
    return event