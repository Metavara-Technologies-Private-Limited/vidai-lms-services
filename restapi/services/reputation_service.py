from django.conf import settings
from restapi.models.reputation import ReviewRequest, ReviewRequestLead
from restapi.models.lead import Lead
from restapi.services.twilio_service import send_sms
from restapi.services.zapier_service import _post_to_webhook
# from restapi.services.zapier_service import (
#     send_to_zapier,
#     send_to_zapier_email,
#     send_to_zapier_reputation_email,
# )
import logging
import re
import uuid
from html import escape
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from urllib.parse import urlparse
from restapi.services.mailchimp_service import get_mailchimp_client

try:
    from mailchimp_marketing.api_client import ApiClientError
except ImportError:  # pragma: no cover
    ApiClientError = Exception

# send_whatsapp does not exist in twilio_service, use send_sms as fallback
send_whatsapp = send_sms

logger = logging.getLogger(__name__)


TWILIO_ERROR_MAP = {
    21211: ("invalid_number", "Phone number is invalid."),
    21408: ("permission_restricted", "SMS is not enabled for this destination country in Twilio settings."),
    21606: ("configuration_error", "Configured sender number is invalid for this channel."),
    21608: ("trial_unverified_number", "This number is not verified in Twilio trial account."),
    21610: ("number_unreachable", "Recipient has opted out and cannot receive SMS."),
    21614: ("number_unreachable", "Phone number does not exist or cannot receive messages."),
    63024: ("number_unreachable", "WhatsApp is not available for this number."),
    63032: ("number_unreachable", "WhatsApp is not available for this number."),
}
def send_to_zapier_reputation(payload: dict):
    """
    Unified Zapier webhook for Email / SMS / WhatsApp
    """
    return _post_to_webhook(
        label="Zapier Reputation Unified",
        webhook_url="https://hooks.zapier.com/hooks/catch/25767405/u771d3l/",
        payload=payload,
        timeout=10,
    )

def validate_phone_number(phone_number):
    """
    Validate phone number format.
    Accepts: +1234567890, 1234567890, or country-code variations
    Returns: (is_valid: bool, formatted_number: str, error_message: str)
    """
    if not phone_number:
        return False, "", "Phone number is empty"
    
    # Remove spaces, hyphens, parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', str(phone_number))
    
    # Check if it contains at least 10 digits
    digits = re.sub(r'\D', '', cleaned)
    
    if len(digits) < 10:
        return False, "", f"Invalid phone number: must have at least 10 digits (got {len(digits)})"
    
    if len(digits) > 15:
        return False, "", f"Invalid phone number: too many digits (got {len(digits)})"
    
    # Ensure it starts with + or is numeric
    if cleaned and not cleaned[0].isdigit() and cleaned[0] != '+':
        return False, "", "Invalid phone number: must start with + or a digit"
    
    return True, cleaned, ""


def normalize_phone_for_twilio(phone_number):
    """
    Convert a validated phone number into an E.164-like format expected by Twilio.
    """
    normalized_input = str(phone_number).strip()
    digits = re.sub(r'\D', '', str(phone_number))

    if normalized_input.startswith('+'):
        return f"+{digits}"

    default_country_code = str(getattr(settings, "TWILIO_DEFAULT_COUNTRY_CODE", "91")).strip().lstrip('+')

    if len(digits) == 10:
        return f"+{default_country_code}{digits}"

    if len(digits) == 11 and digits.startswith('0'):
        return f"+{default_country_code}{digits[1:]}"

    return f"+{digits}"


def get_frontend_base_url():
    frontend_base_url = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
    if not frontend_base_url:
        frontend_base_url = "https://lms-vidaisolutions.com"
    if frontend_base_url:
        parsed = urlparse(frontend_base_url)
        if parsed.scheme and parsed.netloc:
            # Keep only origin so links do not inherit app sub-routes like /settings/integration.
            frontend_base_url = f"{parsed.scheme}://{parsed.netloc}"
    return frontend_base_url


def build_review_link(review_request, lead, feedback_token=None):
    frontend_base_url = get_frontend_base_url()

    if review_request.collect_on == "google":
        # ✅ FIXED: Read Google Review URL from Django settings instead of hardcoded value.
        # Set GOOGLE_REVIEW_URL in settings.py — get it from Google Business Profile > "Ask for reviews"
        # Example: GOOGLE_REVIEW_URL = "https://g.page/r/YOUR_CLINIC_ID/review"
        google_url = str(getattr(settings, "GOOGLE_REVIEW_URL", "") or "").strip()
        if google_url:
            return google_url
        # Fallback: if not configured, send to the form so the lead can still leave feedback
        logger.warning(
            "GOOGLE_REVIEW_URL is not set in Django settings. "
            "Falling back to feedback form for lead %s on request %s.",
            lead.id,
            review_request.id,
        )
        return f"{frontend_base_url}/review/{review_request.id}/{lead.id}"

    if review_request.collect_on in {"form", "both"}:
        # Always send the direct public review form URL to avoid auth redirects.
        return f"{frontend_base_url}/review/{review_request.id}/{lead.id}"
    return ""


def render_message_template(template_text, lead_name, review_link, clinic_name=""):
    message = template_text or ""
    token_map = {
        "{{review_link}}": review_link,
        "{review_link}": review_link,
        "{{feedback_link}}": review_link,
        "{feedback_link}": review_link,
        "[review_link]": review_link,
        "[Review Link]": review_link,
        "{{Review Link}}": review_link,
        "{Review Link}": review_link,
        "{{lead_name}}": lead_name,
        "{lead_name}": lead_name,
        "{{name}}": lead_name,
        "{name}": lead_name,
        "{{patient_name}}": lead_name,
        "{patient_name}": lead_name,
        "{{clinic_name}}": clinic_name,
        "{clinic_name}": clinic_name,
    }
    for token, value in token_map.items():
        message = message.replace(token, value)
    return message


def build_message_body(review_request, lead, review_link):
    clinic_name = str(getattr(review_request.clinic, "name", "") or "Clinic Team").strip()
    if review_request.message:
        message = render_message_template(review_request.message, lead.full_name, review_link, clinic_name)
        if review_link and review_link not in message:
            message = f"{message}\n\n{review_link}".strip()
        return message

    return (
        f"Hi {lead.full_name},\n\n"
        "Thank you for visiting our clinic.\n\n"
        "Please share your experience here:\n"
        f"{review_link}\n\n"
        "Regards,\n"
        "Clinic Team"
    )


def build_email_html_message(lead, message_text, review_link):
    """
    Render rich email content where the first review URL becomes a button
    and any later occurrences remain normal clickable links.
    """
    safe_text = escape(message_text or "")
    safe_link = escape(review_link or "")

    body_html = safe_text.replace("\n", "<br>")

    if safe_link:
        button_html = (
            f'<a href="{safe_link}" '
            'style="display:inline-block;background-color:#4CAF50;color:#ffffff;padding:10px 20px;'
            'text-decoration:none;border-radius:6px;font-weight:600;">Share Review</a>'
        )
        plain_link_html = f'<a href="{safe_link}" style="color:#2563eb;">{safe_link}</a>'

        # First occurrence becomes CTA button.
        body_html = body_html.replace(safe_link, button_html, 1)
        # Remaining occurrences stay as normal links (for footer copy/paste style).
        body_html = body_html.replace(safe_link, plain_link_html)

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #232323;">
            <p>Hi {escape(lead.full_name)},</p>
            <p>{body_html}</p>
        </body>
    </html>
    """


def build_delivery_failure(lead, category, user_message, detail=None, recipient=None, provider_code=None):
    failure = {
        "lead_id": str(lead.id),
        "lead": lead.full_name,
        "category": category,
        "user_message": user_message,
    }

    if recipient:
        failure["recipient"] = recipient
    if detail:
        failure["detail"] = detail
    if provider_code is not None:
        failure["provider_code"] = provider_code

    return failure


def build_delivery_queue(lead, user_message, detail=None, recipient=None):
    queued = {
        "lead_id": str(lead.id),
        "lead": lead.full_name,
        "category": "queued_external",
        "user_message": user_message,
    }

    if recipient:
        queued["recipient"] = recipient
    if detail:
        queued["detail"] = detail

    return queued


def is_email_configured():
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").strip()
    if not backend:
        return False, "EMAIL_BACKEND is not configured"

    smtp_backends = {
        "django.core.mail.backends.smtp.EmailBackend",
        "django.core.mail.backends.smtp.EmailBackend",
    }

    if backend in smtp_backends:
        host = str(getattr(settings, "EMAIL_HOST", "") or "").strip()
        user = str(getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
        password = str(getattr(settings, "EMAIL_HOST_PASSWORD", "") or "").strip()

        if not host:
            return False, "EMAIL_HOST is not configured"
        if not user:
            return False, "EMAIL_HOST_USER is not configured"
        if not password:
            return False, "EMAIL_HOST_PASSWORD is not configured"

    return True, ""


def is_zapier_email_configured():
    # Always return True since we have hardcoded fallback webhook URLs in zapier_service.py
    # This ensures Zapier is always attempted as a fallback when SMTP fails
    return True


def is_mailchimp_configured():
    required_values = [
        str(getattr(settings, "MAILCHIMP_API_KEY", "") or "").strip(),
        str(getattr(settings, "MAILCHIMP_SERVER", "") or "").strip(),
        str(getattr(settings, "MAILCHIMP_AUDIENCE_ID", "") or "").strip(),
        str(getattr(settings, "MAILCHIMP_SENDER_EMAIL", "") or "").strip(),
    ]
    return all(required_values)


def send_review_email_via_mailchimp(review_request, lead, subject, message_html):
    audience_id = str(getattr(settings, "MAILCHIMP_AUDIENCE_ID", "") or "").strip()
    # Mailchimp often rejects campaign send when reply_to is not a verified sender.
    reply_to = str(getattr(settings, "MAILCHIMP_SENDER_EMAIL", "") or "").strip()
    from_name = (
        str(getattr(review_request.clinic, "name", "") or "").strip()
        or "Clinic Team"
    )

    email = str(lead.email or "").strip().lower()
    if not email:
        return False, None, "Lead email is empty"

    client = get_mailchimp_client()

    try:
        # Ensure recipient exists in audience before campaign send.
        client.lists.batch_list_members(
            audience_id,
            {
                "members": [
                    {
                        "email_address": email,
                        "status_if_new": "subscribed",
                        "status": "subscribed",
                    }
                ],
                "update_existing": True,
            },
        )

        segment = client.lists.create_segment(
            audience_id,
            {
                "name": f"reputation-{review_request.id}-{lead.id}",
                "static_segment": [email],
            },
        )
        segment_id = segment.get("id")

        recipients = {"list_id": audience_id}
        if segment_id is not None:
            recipients["segment_opts"] = {"saved_segment_id": segment_id}

        campaign = client.campaigns.create(
            {
                "type": "regular",
                "recipients": recipients,
                "settings": {
                    "subject_line": subject,
                    "from_name": from_name,
                    "reply_to": reply_to,
                    "title": f"Reputation Request - {review_request.request_name}",
                },
            }
        )

        mailchimp_campaign_id = campaign["id"]
        client.campaigns.set_content(mailchimp_campaign_id, {"html": message_html})
        client.campaigns.send(mailchimp_campaign_id)

        return True, mailchimp_campaign_id, ""

    except ApiClientError as exc:
        detail = getattr(exc, "text", None) or str(exc)
        return False, None, detail
    except Exception as exc:  # pragma: no cover
        return False, None, str(exc)


def send_review_email_via_zapier(
    review_request,
    lead,
    sender_email,
    subject,
    message_text,
    message_html,
    review_link,
):
    payload = {
        # Dedicated payload used by the active reputation email Zap.
        "channel": "email",
        "recipient_email": lead.email,
        "patient_name": lead.full_name,
        "clinic_name": str(getattr(review_request.clinic, "name", "") or "").strip(),
        "from_email": sender_email,
        "subject": subject,
        "body": message_text,
        "feedback_link": review_link,

        # Reuse known email-campaign event shape so existing Zapier flows can process it.
        "event": "email_campaign_created",
        "status": "sent",
        "emails": lead.email,
        "campaign_id": str(review_request.id),
        "campaign_name": review_request.request_name,
        "campaign_description": review_request.description,
        "campaign_objective": "reputation_review_request",
        "target_audience": "single_lead",
        "start_date": None,
        "end_date": None,
        "subject": subject,
        "email_body": message_html,
        "sender_email": sender_email,
        "scheduled_at": None,

        # Compatibility fields for custom reputation zaps.
        "mode": "email",
        "review_request_id": str(review_request.id),
        "clinic_id": review_request.clinic_id,
        "request_name": review_request.request_name,
        "lead_id": str(lead.id),
        "lead_name": lead.full_name,
        "to_email": lead.email,
        "message_text": message_text,
        "message_html": message_html,
        "review_link": review_link,
    }

    status_code = send_to_zapier_reputation_email(payload)
    if status_code is not None and 200 <= int(status_code) < 300:
        return True

    status_code = send_to_zapier_email(payload)
    if status_code is not None and 200 <= int(status_code) < 300:
        return True

    status_code = send_to_zapier(payload)
    return status_code is not None and 200 <= int(status_code) < 300


def classify_provider_error(error, mode):
    provider_code = getattr(error, "code", None)
    detail = str(error).strip() or f"Failed to send {mode}."

    if provider_code is None:
        match = re.search(r"errors/(\d{4,6})", detail)
        if match:
            provider_code = int(match.group(1))

    if provider_code in TWILIO_ERROR_MAP:
        category, user_message = TWILIO_ERROR_MAP[provider_code]
        return category, user_message, detail, provider_code

    fallback_message = "Failed to send message. Please verify the number and try again."
    return "provider_error", fallback_message, detail, provider_code


def create_review_request(validated_data):

    lead_ids = validated_data.pop("lead_ids", [])

    # Create Review Request
    review_request = ReviewRequest.objects.create(**validated_data)
    logger.info(f"Created review request: {review_request.id} - Mode: {review_request.mode}, Collect on: {review_request.collect_on}")

    # Fetch Leads
    leads = Lead.objects.filter(id__in=lead_ids)
    total_leads = leads.count()
    
    # Track delivery outcomes
    failed_leads = []
    success_count = 0
    queued_count = 0
    queued_leads = []

    for lead in leads:

        rr_lead = ReviewRequestLead.objects.create(
            review_request=review_request,
            lead=lead
        )

        if not rr_lead.feedback_token:
            rr_lead.feedback_token = uuid.uuid4().hex
            rr_lead.save(update_fields=["feedback_token"])

        # ===============================
        # GENERATE LINK
        # ===============================
        review_link = build_review_link(
            review_request,
            lead,
            feedback_token=rr_lead.feedback_token,
        )

        # Validate that FRONTEND_BASE_URL is set
        if not get_frontend_base_url() and review_request.collect_on in ["form", "both"]:
            error_msg = "FRONTEND_BASE_URL not configured in settings"
            logger.error(error_msg)
            rr_lead.request_sent = False
            rr_lead.save()
            failed_leads.append(
                build_delivery_failure(
                    lead=lead,
                    category="configuration_error",
                    user_message="Review link configuration is missing.",
                    detail=error_msg,
                )
            )
            continue

        # ===============================
        # PREPARE MESSAGE
        # ===============================
        message_text = build_message_body(review_request, lead, review_link)

        message_html = build_email_html_message(lead, message_text, review_link)

        # ===============================
        # EMAIL
        # ===============================
        if review_request.mode == "email":
            if not lead.email:
                error_msg = f"Lead {lead.full_name} has no email address"
                logger.warning(error_msg)
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="missing_email",
                        user_message="Email address is missing.",
                        detail="No email address",
                    )
                )
                continue

            try:
                validate_email(lead.email)
            except ValidationError:
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="invalid_email",
                        user_message="Email address is invalid.",
                        detail=f"Invalid email format: {lead.email}",
                        recipient=lead.email,
                    )
                )
                continue

            email_configured, email_config_error = is_email_configured()
            zapier_configured = is_zapier_email_configured()
            mailchimp_configured = is_mailchimp_configured()

            try:
                sender_email = (
                    getattr(review_request.clinic, "email", "")
                    or getattr(settings, "DEFAULT_FROM_EMAIL", "")
                    or settings.EMAIL_HOST_USER
                    or "noreply@clinic.com"
                )

                smtp_error_detail = ""

                # Fallback to Zapier flow when configured.
                if zapier_configured:
                    payload = {
                        "channel": "email",
                        "recipient_email": lead.email,
                        "patient_name": lead.full_name,
                        "clinic_name": str(getattr(review_request.clinic, "name", "") or "").strip(),
                        "from_email": sender_email,
                        "subject": review_request.subject or "Share Your Experience",
                        "body": message_text,
                        "feedback_link": review_link,
                        "email_body": message_html,
                        "message_html": message_html,
                        "body_html": message_html,
                        "html": message_html,
                        "share_review_button_text": "Share Review",
                        "share_review_button_url": review_link,
                        "plain_review_link": review_link,
                    }

                    response = send_to_zapier_reputation(payload)

                    if response and response.status_code in [200, 201]:
                        rr_lead.request_sent = True
                        rr_lead.sent_link = review_link
                        rr_lead.save()
                        logger.info(
                            "Email accepted by Zapier for %s (Lead: %s) - Link: %s",
                            lead.email,
                            lead.full_name,
                            review_link,
                        )
                        success_count += 1
                        continue

                if email_configured:
                    send_mail(
                        subject=review_request.subject or "Share Your Experience",
                        message=message_text,
                        from_email=sender_email,
                        recipient_list=[lead.email],
                        html_message=message_html,
                        fail_silently=False,
                    )

                    rr_lead.request_sent = True
                    rr_lead.sent_link = review_link
                    rr_lead.save()

                    logger.info(f"Email sent to {lead.email} (Lead: {lead.full_name}) - Link: {review_link}")
                    success_count += 1
                    continue

                smtp_error_detail = email_config_error or "SMTP is not configured"

                logger.error(
                    "Email could not be sent. Mailchimp configured=%s, Zapier configured=%s, SMTP configured=%s, SMTP detail=%s",
                    mailchimp_configured,
                    zapier_configured,
                    email_configured,
                    smtp_error_detail,
                )
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="configuration_error",
                        user_message="Email service is not configured.",
                        detail=f"{smtp_error_detail}; Zapier fallback failed",
                        recipient=lead.email,
                    )
                )

            except Exception as e:
                error_msg = f"Failed to send email: {str(e)}"
                logger.error(f"{error_msg} - Lead: {lead.full_name}, Email: {lead.email}")
                try:
                    sender_email = (
                        getattr(review_request.clinic, "email", "")
                        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
                        or settings.EMAIL_HOST_USER
                        or "noreply@clinic.com"
                    )

                except Exception as zapier_error:
                    logger.error("Zapier fallback failed after SMTP error: %s", zapier_error)

                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="provider_error",
                        user_message="Failed to send email.",
                        detail=str(e),
                        recipient=lead.email,
                    )
                )

        # ===============================
        # SMS
        # ===============================
        elif review_request.mode == "sms":
            if not lead.contact_no:
                error_msg = f"Lead {lead.full_name} has no phone number"
                logger.warning(error_msg)
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="missing_phone",
                        user_message="Phone number is missing.",
                        detail="No phone number",
                    )
                )
                continue

            # Validate phone number
            is_valid, formatted_phone, validation_error = validate_phone_number(lead.contact_no)
            
            if not is_valid:
                logger.warning(f"Invalid SMS phone number for {lead.full_name}: {validation_error}")
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="invalid_number",
                        user_message="Phone number is invalid.",
                        detail=validation_error,
                        recipient=lead.contact_no,
                    )
                )
                continue

            try:
                twilio_number = normalize_phone_for_twilio(formatted_phone)
                payload = {
                    "channel": "sms",
                    "recipient_phone": twilio_number,
                    "patient_name": lead.full_name,
                    "clinic_name": str(getattr(review_request.clinic, "name", "") or "").strip(),
                    "body": message_text,
                    "feedback_link": review_link
                }

                response = send_to_zapier_reputation(payload)

                if response and response.status_code in [200, 201]:
                    rr_lead.request_sent = True
                    rr_lead.sent_link = review_link
                    rr_lead.save()
                    success_count += 1
                    continue

            except Exception as e:
                error_msg = f"Failed to send SMS: {str(e)}"
                logger.error(f"{error_msg} - Lead: {lead.full_name}, Phone: {formatted_phone}")
                rr_lead.request_sent = False
                rr_lead.save()
                category, user_message, detail, provider_code = classify_provider_error(e, "sms")
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category=category,
                        user_message=user_message,
                        detail=detail,
                        recipient=formatted_phone,
                        provider_code=provider_code,
                    )
                )

        # ===============================
        # WHATSAPP
        # ===============================
        elif review_request.mode == "whatsapp":
            if not lead.contact_no:
                error_msg = f"Lead {lead.full_name} has no phone number"
                logger.warning(error_msg)
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="missing_phone",
                        user_message="Phone number is missing.",
                        detail="No phone number",
                    )
                )
                continue

            # Validate phone number
            is_valid, formatted_phone, validation_error = validate_phone_number(lead.contact_no)
            
            if not is_valid:
                logger.warning(f"Invalid WhatsApp phone number for {lead.full_name}: {validation_error}")
                rr_lead.request_sent = False
                rr_lead.save()
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category="invalid_number",
                        user_message="Phone number is invalid.",
                        detail=validation_error,
                        recipient=lead.contact_no,
                    )
                )
                continue

            try:
                twilio_number = normalize_phone_for_twilio(formatted_phone)
                payload = {
                    "channel": "whatsapp",
                    "recipient_phone": twilio_number,
                    "patient_name": lead.full_name,
                    "clinic_name": str(getattr(review_request.clinic, "name", "") or "").strip(),
                    "body": message_text,
                    "feedback_link": review_link
                }

                response = send_to_zapier_reputation(payload)

                if response and response.status_code in [200, 201]:
                    rr_lead.request_sent = True
                    rr_lead.sent_link = review_link
                    rr_lead.save()
                    success_count += 1

                    logger.info(f"WhatsApp sent via Zapier to {twilio_number} (Lead: {lead.full_name}) - Link: {review_link}")
                    continue

            except Exception as e:
                error_msg = f"Failed to send WhatsApp: {str(e)}"
                logger.error(f"{error_msg} - Lead: {lead.full_name}, Phone: {formatted_phone}")
                rr_lead.request_sent = False
                rr_lead.save()
                category, user_message, detail, provider_code = classify_provider_error(e, "whatsapp")
                failed_leads.append(
                    build_delivery_failure(
                        lead=lead,
                        category=category,
                        user_message=user_message,
                        detail=detail,
                        recipient=formatted_phone,
                        provider_code=provider_code,
                    )
                )

    logger.info(f"Review request {review_request.id} completed: {success_count} successful, {len(failed_leads)} failed")
    
    if failed_leads:
        logger.warning(f"Failed sends: {failed_leads}")

    review_request._delivery_report = {
        "total_leads": total_leads,
        "success_count": success_count,
        "queued_count": queued_count,
        "failed_count": len(failed_leads),
        "queued_leads": queued_leads,
        "failed_leads": failed_leads,
    }
    
    return review_request