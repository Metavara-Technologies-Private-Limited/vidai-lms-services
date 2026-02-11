import uuid
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from restapi.models import Ticket, Document, TicketTimeline, Lab

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

    # Create main ticket record
    ticket_instance = Ticket.objects.create(
        ticket_no=generate_ticket_number(),
        **validated_data
    )

    # Save attached documents
    for document_item in attached_documents:
        Document.objects.create(
            ticket=ticket_instance,
            file=document_item.get("file")
        )

    # Create initial timeline entry
    TicketTimeline.objects.create(
        ticket=ticket_instance,
        action="Ticket Created",
        done_by=ticket_instance.assigned_to
    )

    return ticket_instance


# ============================================================
# UPDATE TICKET SERVICE
# ============================================================
@transaction.atomic
def update_ticket_service(ticket_instance, validated_data):

    attached_documents = validated_data.pop("documents", [])

    # Update basic ticket fields
    for field_name, field_value in validated_data.items():
        setattr(ticket_instance, field_name, field_value)

    ticket_instance.save()

    # Validate and update documents
    existing_documents = {
        str(document.id): document
        for document in ticket_instance.documents.all()
    }

    for document_item in attached_documents:

        document_identifier = str(document_item.get("id"))

        # Validation: Ensure document id is provided
        if not document_identifier:
            raise ValidationError(
                "Document id is required when updating documents."
            )

        # Validation: Ensure document belongs to this ticket
        if document_identifier not in existing_documents:
            raise ValidationError(
                f"Document id {document_identifier} does not belong to this ticket."
            )

        document_instance = existing_documents[document_identifier]
        document_instance.file = document_item.get(
            "file",
            document_instance.file
        )
        document_instance.save()

    # Handle status change and timeline tracking
    if "status" in validated_data:

        TicketTimeline.objects.create(
            ticket=ticket_instance,
            action=f"Status changed to {ticket_instance.status}",
            done_by=ticket_instance.assigned_to
        )

        if ticket_instance.status == "resolved":
            ticket_instance.resolved_at = timezone.now()

        if ticket_instance.status == "closed":
            ticket_instance.closed_at = timezone.now()

        ticket_instance.save()

    ticket_instance.refresh_from_db()

    return ticket_instance
