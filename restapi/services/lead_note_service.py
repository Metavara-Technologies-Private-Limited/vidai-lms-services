from django.db import transaction
from rest_framework.exceptions import ValidationError

from restapi.models import LeadNote


# =====================================================
# CREATE LEAD NOTE
# =====================================================

@transaction.atomic
def create_lead_note(validated_data):
    """
    Creates a new note for a Lead.

    Business Rules:
    - Lead must exist
    - created_by must exist
    """

    return LeadNote.objects.create(**validated_data)


# =====================================================
# UPDATE LEAD NOTE
# =====================================================

@transaction.atomic
def update_lead_note(instance, validated_data):
    """
    Updates an existing Lead Note.

    Only allowed if note is not deleted.
    """

    if instance.is_deleted:
        raise ValidationError("Cannot update a deleted note.")

    for field, value in validated_data.items():
        setattr(instance, field, value)

    instance.save()
    instance.refresh_from_db()

    return instance


# =====================================================
# SOFT DELETE LEAD NOTE
# =====================================================

@transaction.atomic
def delete_lead_note(instance):
    """
    Soft deletes a Lead Note.
    """

    if instance.is_deleted:
        raise ValidationError("Note is already deleted.")

    instance.is_deleted = True
    instance.is_active = False
    instance.save()

    return instance
