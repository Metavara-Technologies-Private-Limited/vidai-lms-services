from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from restapi.models import (
    Event,
    EventSchedule,
)

from restapi.services.event_service import (
    validate_event_create,
    create_event,
)


class EventScheduleReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSchedule
        fields = [
            "type",
            "from_time",
            "to_time",
            "one_time_date",
            "start_date",
            "end_date",
            "months",
            "days",
            "recurring_duration",
        ]


# =========================
# Event READ Serializer
# =========================
class EventReadSerializer(serializers.ModelSerializer):
    schedule = serializers.SerializerMethodField()
    equipments = serializers.SerializerMethodField()
    parameters = serializers.SerializerMethodField()

    assignment = serializers.CharField(
        source="assignment.emp_name",
        read_only=True
    )
    department = serializers.CharField(
        source="department.name",
        read_only=True
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "event_name",
            "description",
            "department",
            "assignment",
            "schedule",
            "equipments",
            "parameters",
            "created_at",
        ]

    def get_schedule(self, event_instance):
        schedule = (
            event_instance.eventschedule_set
            .order_by("-created_at")
            .first()
        )
        if not schedule:
            return None
        return EventScheduleReadSerializer(schedule).data

    def get_equipments(self, event_instance):
        return list(
            event_instance.eventequipment_set
            .select_related("equipment_details__equipment")
            .values(
                "equipment_details__id",
                "equipment_details__equipment_num",
                "equipment_details__equipment__id",
                "equipment_details__equipment__equipment_name",
            )
        )

    def get_parameters(self, event_instance):
        return list(
            event_instance.eventparameter_set
            .select_related("parameter")
            .values(
                "parameter__id",
                "parameter__parameter_name",
            )
        )


# =========================
# Event Create Serializer
# =========================
class EventScheduleCreateSerializer(serializers.Serializer):
    type = serializers.IntegerField()
    from_time = serializers.DateTimeField()
    to_time = serializers.DateTimeField()

    one_time_date = serializers.DateTimeField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)

    months = serializers.JSONField(required=False, allow_null=True)
    days = serializers.JSONField(required=False, allow_null=True)
    recurring_duration = serializers.IntegerField(required=False, allow_null=True)


# =========================
# Event Create Serializer
# =========================
class EventCreateSerializer(serializers.Serializer):
    department_id = serializers.IntegerField()
    assignment_id = serializers.IntegerField(required=False, allow_null=True)
    event_name = serializers.CharField()
    description = serializers.CharField()

    # ✅ CHANGED
    equipment_details_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    parameter_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    schedule = EventScheduleCreateSerializer()

    # ---------------- VALIDATION ----------------
    def validate(self, attrs):
        return validate_event_create(self, attrs)

    # ---------------- CREATE ----------------
    def create(self, validated_data):
        return create_event(validated_data)
