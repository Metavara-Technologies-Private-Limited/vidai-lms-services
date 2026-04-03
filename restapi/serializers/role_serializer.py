from rest_framework import serializers
from restapi.models import Role, RolePermission
from restapi.services.role_service import create_role, update_role


class RolePermissionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = RolePermission
        fields = [
            "id",
            "module_key",
            "category_key",
            "subcategory_key",
            "can_view",
            "can_add",
            "can_edit",
            "can_print",
        ]


class RoleSerializer(serializers.ModelSerializer):

    permissions = RolePermissionSerializer(many=True)

    class Meta:
        model = Role
        fields = ["id", "name", "permissions"]

    # ✅ VALIDATION ADDED
    def validate(self, data):
        permissions = data.get("permissions", [])
        seen = set()

        for perm in permissions:
            key = (
                perm.get("module_key"),
                perm.get("category_key"),
                perm.get("subcategory_key"),
            )

            if key in seen:
                raise serializers.ValidationError(
                    "Duplicate permission combination found"
                )

            seen.add(key)

        return data

    def create(self, validated_data):
        return create_role(validated_data)

    def update(self, instance, validated_data):
        return update_role(instance, validated_data)


# ✅ CLEAN READ SERIALIZER
class RoleReadSerializer(serializers.ModelSerializer):

    permissions = RolePermissionSerializer(many=True)

    class Meta:
        model = Role
        fields = ["id", "name", "permissions"]