from django.conf import settings
from restapi.models.reputation import ReviewRequest, ReviewRequestLead
from restapi.models.lead import Lead
from restapi.services.twilio_service import send_sms, send_whatsapp
import logging
import re
from django.core.mail import send_mail

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


def build_review_link(review_request, lead):
    if review_request.collect_on == "google":
        return "https://g.page/review/your-clinic"
    if review_request.collect_on == "form":
        return f"{settings.FRONTEND_BASE_URL}/review/{review_request.id}/{lead.id}"
    if review_request.collect_on == "both":
        return f"{settings.FRONTEND_BASE_URL}/rating-gate/{review_request.id}"
    return ""


def render_message_template(template_text, lead_name, review_link):
    message = template_text or ""
    token_map = {
        "{{review_link}}": review_link,
        "{review_link}": review_link,
        "[review_link]": review_link,
        "{{lead_name}}": lead_name,
        "{lead_name}": lead_name,
        "{{name}}": lead_name,
        "{name}": lead_name,
    }
    for token, value in token_map.items():
        message = message.replace(token, value)
    return message


def build_message_body(review_request, lead, review_link):
    if review_request.message:
        message = render_message_template(review_request.message, lead.full_name, review_link)
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
    
    # Track failed sends
    failed_leads = []
    success_count = 0

    for lead in leads:

        rr_lead = ReviewRequestLead.objects.create(
            review_request=review_request,
            lead=lead
        )

        # ===============================
        # GENERATE LINK
        # ===============================
        review_link = build_review_link(review_request, lead)

        # Validate that FRONTEND_BASE_URL is set
        if not settings.FRONTEND_BASE_URL and review_request.collect_on in ["form", "both"]:
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

        message_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <p>Hi {lead.full_name},</p>
                
            <p>{message_text.replace(chr(10), '<br>')}</p>
                
                <p>Please share your experience here:</p>
                <p><a href="{review_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Share Review</a></p>
                
                <p style="color: #666; font-size: 12px;">Or copy this link: <code>{review_link}</code></p>
                
                <p>Regards,<br>Clinic Team</p>
            </body>
        </html>
        """

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
                send_mail(
                    subject=review_request.subject or "Share Your Experience",
                    message=message_text,
                    from_email=settings.EMAIL_HOST_USER or "noreply@clinic.com",
                    recipient_list=[lead.email],
                    html_message=message_html,
                    fail_silently=False,
                )
                
                rr_lead.request_sent = True
                rr_lead.sent_link = review_link
                rr_lead.save()
                
                logger.info(f"Email sent to {lead.email} (Lead: {lead.full_name}) - Link: {review_link}")
                success_count += 1

            except Exception as e:
                error_msg = f"Failed to send email: {str(e)}"
                logger.error(f"{error_msg} - Lead: {lead.full_name}, Email: {lead.email}")
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
                send_sms(
                    lead_uuid=lead.id,
                    to_number=twilio_number,
                    message_body=message_text,
                )
                
                rr_lead.request_sent = True
                rr_lead.sent_link = review_link
                rr_lead.save()
                success_count += 1

                logger.info(f"SMS sent to {twilio_number} (Lead: {lead.full_name}) - Link: {review_link}")

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
                send_whatsapp(
                    lead_uuid=lead.id,
                    to_number=twilio_number,
                    message_body=message_text,
                )
                
                rr_lead.request_sent = True
                rr_lead.sent_link = review_link
                rr_lead.save()
                success_count += 1

                logger.info(f"WhatsApp sent to {twilio_number} (Lead: {lead.full_name}) - Link: {review_link}")

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
        "failed_count": len(failed_leads),
        "failed_leads": failed_leads,
    }
    
    return review_request