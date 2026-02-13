from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import LeadNote
from restapi.services.lead_note_service import (
    create_lead_note,
    update_lead_note,
)


# =====================================================
# LEAD NOTE READ SERIALIZER
# =====================================================

class LeadNoteReadSerializer(serializers.ModelSerializer):
    """
    Read Serializer for Lead Notes.

    Used when returning notes to frontend.
    """

    class Meta:
        model = LeadNote
        fields = "__all__"


# =====================================================
# LEAD NOTE WRITE SERIALIZER
# =====================================================

class LeadNoteSerializer(serializers.ModelSerializer):
    """
    Write Serializer for Lead Notes.

    Responsibilities:
    - Validate note content
    - Delegate business logic to service layer
    """

    class Meta:
        model = LeadNote
        fields = "__all__"

    # -------------------------------------------------
    # FIELD LEVEL VALIDATION
    # -------------------------------------------------

    def validate_note(self, value):
        """
        Note content must not be empty.
        """
        if not value or not value.strip():
            raise ValidationError("Note content cannot be empty.")
        return value

    # -------------------------------------------------
    # CREATE
    # -------------------------------------------------

    def create(self, validated_data):
        return create_lead_note(validated_data)

    # -------------------------------------------------
    # UPDATE
    # -------------------------------------------------

    def update(self, instance, validated_data):
        return update_lead_note(instance, validated_data)
