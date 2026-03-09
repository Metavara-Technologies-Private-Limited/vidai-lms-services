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
    Uses batch operation for efficiency.
    """
    client = get_mailchimp_client()

    members = [
        {
            "email_address": email,
            "status_if_new": "subscribed",
            "status": "subscribed",
        }
        for email in emails
    ]

    try:
        response = client.lists.batch_list_members(
            settings.MAILCHIMP_AUDIENCE_ID,
            {"members": members, "update_existing": True},
        )
        logger.info(
            f"Mailchimp sync: {response.get('total_created')} created, {response.get('total_updated')} updated"
        )
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

        # Step 3: Always send immediately
        # NOTE: Scheduling requires Mailchimp paid plan (Standard+)
        # For now we send immediately regardless of scheduled_at
        # TODO: Upgrade to paid plan to enable scheduling
        client.campaigns.send(mailchimp_campaign_id)
        logger.info(f"Mailchimp campaign sent: {mailchimp_campaign_id}")

        return mailchimp_campaign_id

    except ApiClientError as e:
        logger.error(f"Mailchimp campaign create/send failed: {e.text}")
        raise


def get_mailchimp_campaign_report(mailchimp_campaign_id: str):
    client = get_mailchimp_client()

    try:
        report = client.reports.get_campaign_report(mailchimp_campaign_id)

        bounces = report.get("bounces", {})
        hard_bounces = bounces.get("hard", {})
        soft_bounces = bounces.get("soft", {})

        return {
            "emails_sent": report.get("emails_sent", 0),
            "opens": report.get("opens", {}).get("unique_opens", 0),
            "clicks": report.get("clicks", {}).get("unique_clicks", 0),
            "bounces": (
                hard_bounces.get("bounce_count", 0)
                + soft_bounces.get("bounce_count", 0)
            ),
            "unsubscribes": report.get("unsubscribed", 0),
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
