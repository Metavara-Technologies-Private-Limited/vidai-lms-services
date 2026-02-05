from rest_framework import serializers
from restapi.models import Task_Event


# =========================
# WRITE Serializer
# =========================
class TaskEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task_Event
        fields = [
            "id",
            "name",
            "dep",
            "is_deleted",
            "created_at",
            "modified_at"
        ]
        read_only_fields = ("created_at", "modified_at")




# =========================
# READ Serializer (optional but recommended)
# =========================
class TaskEventReadSerializer(serializers.ModelSerializer):
    dep_name = serializers.CharField(source="dep.name", read_only=True)

    class Meta:
        model = Task_Event
        fields = [
            "id",
            "name",
            "dep",
            "dep_name",
            "is_deleted",
            "created_at",
            "modified_at"
        ]
