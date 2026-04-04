from django.db import transaction
from rest_framework.exceptions import ValidationError
from restapi.models import Role, RolePermission


@transaction.atomic
def create_role(validated_data):

    permissions_data = validated_data.pop("permissions", [])

    role_name = validated_data["name"].strip()

    if Role.objects.filter(name__iexact=role_name).exists():
        raise ValidationError({"name": "Role already exists"})

    role = Role.objects.create(name=role_name)

    RolePermission.objects.bulk_create([
        RolePermission(
            role=role,
            module_key=perm["module_key"],
            category_key=perm["category_key"],
            subcategory_key=perm.get("subcategory_key"),
            can_view=perm.get("can_view", False),
            can_add=perm.get("can_add", False),
            can_edit=perm.get("can_edit", False),
            can_print=perm.get("can_print", False),
        )
        for perm in permissions_data
    ])

    return role


@transaction.atomic
def update_role(instance, validated_data):

    permissions_data = validated_data.pop("permissions", [])

    if "name" in validated_data:
        new_name = validated_data["name"].strip()

        if Role.objects.filter(name__iexact=new_name).exclude(id=instance.id).exists():
            raise ValidationError({"name": "Role already exists"})

        instance.name = new_name

    instance.save()

    existing_permissions = {
        perm.id: perm for perm in instance.permissions.all()
    }

    incoming_ids = []

    for perm_data in permissions_data:
        perm_id = perm_data.get("id")

        if perm_id:
            if perm_id not in existing_permissions:
                raise ValidationError("Invalid permission id")

            perm = existing_permissions[perm_id]

            perm.module_key = perm_data.get("module_key", perm.module_key)
            perm.category_key = perm_data.get("category_key", perm.category_key)
            perm.subcategory_key = perm_data.get("subcategory_key", perm.subcategory_key)
            perm.can_view = perm_data.get("can_view", perm.can_view)
            perm.can_add = perm_data.get("can_add", perm.can_add)
            perm.can_edit = perm_data.get("can_edit", perm.can_edit)
            perm.can_print = perm_data.get("can_print", perm.can_print)

            perm.save()
            incoming_ids.append(perm_id)

        else:
            new_perm = RolePermission.objects.create(
                role=instance,
                module_key=perm_data["module_key"],
                category_key=perm_data["category_key"],
                subcategory_key=perm_data.get("subcategory_key"),
                can_view=perm_data.get("can_view", False),
                can_add=perm_data.get("can_add", False),
                can_edit=perm_data.get("can_edit", False),
                can_print=perm_data.get("can_print", False),
            )

            incoming_ids.append(new_perm.id)

    instance.permissions.exclude(id__in=incoming_ids).delete()

    return instance