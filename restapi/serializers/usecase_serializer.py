from rest_framework import serializers
from restapi.models import UseCase


class UseCaseSerializer(serializers.ModelSerializer):

    class Meta:
        model = UseCase
        fields = "__all__"
        read_only_fields = ("id", "created_at", "clinic")

    def validate(self, data):
        request = self.context.get("request")

        # ✅ GET CLINIC FROM CONTEXT (IMPORTANT)
        clinic = getattr(self.instance, "clinic", None)

        if request and hasattr(request, "clinic"):
            clinic = request.clinic

        if not clinic:
            clinic = data.get("clinic")

        name = data.get("name") or getattr(self.instance, "name", None)

        if not clinic:
            raise serializers.ValidationError({"clinic": "Clinic is required"})

        if not name or not name.strip():
            raise serializers.ValidationError({"name": "UseCase name is required"})

        qs = UseCase.objects.filter(
            clinic=clinic,
            name=name.strip(),
            is_active=True
        )

        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "UseCase already exists for this clinic"
            })

        data["name"] = name.strip()
        return data