from rest_framework import serializers

from restapi.models import LeadFormField


class LeadFormFieldSerializer(serializers.ModelSerializer):
    stage_field_type = serializers.SerializerMethodField()

    class Meta:
        model = LeadFormField
        fields = [
            "id",
            "field_key",
            "model_field",
            "field_label",
            "field_type",
            "stage_field_type",
            "options_source",
            "form_step",
            "section",
            "sort_order",
            "is_required",
            "is_locked",
            "is_active",
        ]

    def get_stage_field_type(self, obj):
        return obj.stage_field_type
