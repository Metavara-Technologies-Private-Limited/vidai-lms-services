import uuid
from django.core.mail import EmailMessage
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from restapi.models import Ticket, Document, TicketTimeline, Lab, TicketReply


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

    return ticket_instance


# ============================================================
# UPDATE TICKET SERVICE
# ============================================================
@transaction.atomic
def update_ticket_service(ticket_instance, validated_data):

    attached_documents = validated_data.pop("documents", [])

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