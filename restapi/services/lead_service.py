from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import strip_tags
from django.db import transaction
from django.shortcuts import get_object_or_404

from restapi.models import LeadEmail


def _clean_body(text: str) -> str:
    """
    Convert any HTML in email_body to plain text before sending.
    Handles:
      - Normal HTML:          <p>hello</p>         → hello
      - Double-encoded HTML:  &lt;p&gt;hello&lt;/p&gt; → hello
      - Already plain text:   hello                 → hello
    """
    if not text:
        return ""

    # Step 1 — decode double-encoded entities (&lt;p&gt; → <p>)
    decoded_text = (
        text
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    # Step 2 — strip all HTML tags using Django's built-in strip_tags
    plain_text = strip_tags(decoded_text)

    # Step 3 — collapse excessive blank lines
    import re as regex
    plain_text = regex.sub(r"\n{3,}", "\n\n", plain_text)

    return plain_text.strip()


@transaction.atomic
def send_lead_email(email_id):

    email_object = get_object_or_404(LeadEmail, id=email_id)

    # Prevent resending
    if email_object.status == "SENT":
        raise Exception("Email already sent")

    # Check lead email exists
    if not email_object.lead.email:
        raise Exception("Lead does not have a valid email address")

    try:
        # Always send as plain text
        plain_body_text = _clean_body(email_object.email_body)

        send_mail(
            subject=email_object.subject,
            message=plain_body_text,
            from_email=email_object.sender_email,
            recipient_list=[email_object.lead.email],
            fail_silently=False,
        )

        # Save cleaned body
        email_object.email_body = plain_body_text
        email_object.status = "SENT"
        email_object.sent_at = timezone.now()
        email_object.failed_reason = None
        email_object.save(
            update_fields=["email_body", "status", "sent_at", "failed_reason"]
        )

        return email_object

    except Exception as exception:
        email_object.status = "FAILED"
        email_object.failed_reason = str(exception)
        email_object.save(update_fields=["status", "failed_reason"])

        raise exception