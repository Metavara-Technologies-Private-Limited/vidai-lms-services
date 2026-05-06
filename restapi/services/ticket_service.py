import logging
import requests
import uuid
from django.core.mail import EmailMessage
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.exceptions import ValidationError

from restapi.models import Ticket, Document, TicketTimeline, Lab, TicketReply, Employee

logger = logging.getLogger(__name__)

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/27387148/uv798n7/"


def _clean_email_body(text):
    if not text:
        return ""

    decoded = (
        str(text)
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&nbsp;", " ")
    )

    plain = strip_tags(decoded)
    return plain.strip()


def _build_ticket_webhook_payload(ticket, event, clinic_name, to, cc, email_body):
    return {
        "event": event or "ticket_created",
        "clinicName": clinic_name,
        "to": to or [],
        "cc": cc or [],
        "email_body": _clean_email_body(email_body),
        "ticket_id": str(ticket.id),
        "ticket_no": ticket.ticket_no,
        "subject": ticket.subject,
        "description": ticket.description,
        "requested_by": ticket.requested_by,
        "assigned_to_name": ticket.assigned_to_name,
        "priority": ticket.priority,
        "status": ticket.status,
        "type": ticket.type,
        "due_date": ticket.due_date.isoformat() if ticket.due_date else None,
    }


def _resolve_assignee_email(assignee_id):
    if not assignee_id:
        return None

    employee = Employee.objects.filter(id=assignee_id).select_related("user").first()
    if not employee:
        return None

    if employee.email:
        return employee.email.strip()

    if getattr(employee.user, "email", None):
        return str(employee.user.email).strip()

    return None


def _send_assignment_notification(ticket, assignee_id, assignee_name=None):
    email_address = _resolve_assignee_email(assignee_id)
    if not email_address or "@" not in email_address:
        return

    recipient_name = assignee_name or ticket.assigned_to_name or "User"
    subject = f"You are assigned to ticket {ticket.ticket_no}"
    body = (
        f"Hello {recipient_name},\n\n"
        "You have been assigned to the following ticket:\n\n"
        f"Ticket No: {ticket.ticket_no}\n"
        f"Subject: {ticket.subject}\n"
        f"Description: {ticket.description}\n"
        f"Status: {ticket.status}\n"
        f"Priority: {ticket.priority}\n\n"
        "Please review the ticket and take the next steps.\n\n"
        "Regards,\n"
        "Support Team"
    )

    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL,
            to=[email_address],
        )
        email.content_subtype = "plain"
        email.send(fail_silently=True)
    except Exception as exc:
        logger.error(f"Failed to send assignment notification email: {str(exc)}")


def _send_ticket_webhook(payload):
    if not payload.get("to"):
        return

    try:
        response = requests.post(
            ZAPIER_WEBHOOK_URL,
            json=payload,
            timeout=5,
        )

        logger.info(f"Ticket Zapier webhook response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise Exception(f"Zapier webhook failed with status code {response.status_code}")

    except Exception as exc:
        logger.error(f"Failed to send ticket webhook to Zapier: {str(exc)}")



# ============================================================
# CREATE LAB
# ============================================================
@transaction.atomic
def create_lab_service(validated_data):
    lab = Lab.objects.create(**validated_data)
    return lab


# ============================================================
# UPDATE LAB
# ============================================================
@transaction.atomic
def update_lab_service(instance, validated_data):
    for field, value in validated_data.items():
        setattr(instance, field, value)
    instance.save()
    return instance


# ============================================================
# GENERATE UNIQUE TICKET NUMBER
# ============================================================
def generate_ticket_number():
    return f"TICKET-{uuid.uuid4().hex[:6].upper()}"


# ============================================================
# CREATE TICKET SERVICE
# ============================================================
@transaction.atomic
def create_ticket_service(validated_data):

    attached_documents = validated_data.pop("documents", [])
    event = validated_data.pop("event", None)
    clinic_name = validated_data.pop("clinicName", None)
    to = validated_data.pop("to", None)
    cc = validated_data.pop("cc", [])
    email_body = validated_data.pop("email_body", None)

    # Create ticket
    ticket_instance = Ticket.objects.create(
        ticket_no=generate_ticket_number(),
        **validated_data
    )

    # Save documents
    for document_item in attached_documents:
        Document.objects.create(
            ticket=ticket_instance,
            file=document_item.get("file")
        )

    # ✅ Timeline (FIXED)
    TicketTimeline.objects.create(
        ticket=ticket_instance,
        action="Ticket Created",
        done_by_id=ticket_instance.assigned_to_id,
        done_by_name=ticket_instance.assigned_to_name
    )

    try:
        _send_ticket_webhook(
            _build_ticket_webhook_payload(
                ticket_instance,
                event,
                clinic_name,
                to,
                cc,
                email_body,
            )
        )
    except Exception:
        # Keep ticket creation successful even if Zapier delivery fails.
        logger.warning("Ticket created but Zapier webhook failed.")

    return ticket_instance


# ============================================================
# UPDATE TICKET SERVICE
# ============================================================
@transaction.atomic
def update_ticket_service(ticket_instance, validated_data):
    print("🔥 validated_data:", validated_data)
    attached_documents = validated_data.pop("documents", [])
    event = validated_data.pop("event", None)
    clinic_name = validated_data.pop("clinicName", None)
    to = validated_data.pop("to", None)
    cc = validated_data.pop("cc", [])
    email_body = validated_data.pop("email_body", None)

    # Update fields
    for field_name, field_value in validated_data.items():
        setattr(ticket_instance, field_name, field_value)

    ticket_instance.save()

    # Update documents
    existing_documents = {
        str(document.id): document
        for document in ticket_instance.documents.all()
    }

    for document_item in attached_documents:
        document_identifier = str(document_item.get("id"))

        if not document_identifier:
            raise ValidationError("Document id is required when updating documents.")

        if document_identifier not in existing_documents:
            raise ValidationError(
                f"Document id {document_identifier} does not belong to this ticket."
            )

        document_instance = existing_documents[document_identifier]
        document_instance.file = document_item.get("file", document_instance.file)
        document_instance.save()

    # Status change tracking
    if "status" in validated_data:

        TicketTimeline.objects.create(
            ticket=ticket_instance,
            action=f"Status changed to {ticket_instance.status}",
            done_by_id=ticket_instance.assigned_to_id,
            done_by_name=ticket_instance.assigned_to_name
        )

        if ticket_instance.status == "resolved":
            ticket_instance.resolved_at = timezone.now()

        if ticket_instance.status == "closed":
            ticket_instance.closed_at = timezone.now()

        ticket_instance.save()

    try:
        _send_ticket_webhook(
            _build_ticket_webhook_payload(
                ticket_instance,
                event,
                clinic_name,
                to,
                cc,
                email_body,
            )
        )
    except Exception:
        logger.warning("Ticket updated but Zapier webhook failed.")

    ticket_instance.refresh_from_db()
    return ticket_instance


# ============================================================
# SEND TICKET REPLY SERVICE
# ============================================================
@transaction.atomic
def send_ticket_reply_service(
    ticket,
    subject,
    message,
    to_emails,
    cc_emails,
    bcc_emails,
    sent_by=None
):

    reply = TicketReply.objects.create(
        ticket=ticket,
        subject=subject,
        message=message,
        to_emails=to_emails,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
        sent_by=sent_by,
        status="sent",
    )

    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=to_emails,
            cc=cc_emails,
            bcc=bcc_emails,
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)

        # ✅ Timeline (FIXED)
        TicketTimeline.objects.create(
            ticket=ticket,
            action="Reply sent via email",
            done_by_id=sent_by,
            done_by_name=str(sent_by) if sent_by else None
        )

    except Exception as exc:
        reply.status = "failed"
        reply.failed_reason = str(exc)
        reply.save(update_fields=["status", "failed_reason"])
        raise exc

    return reply