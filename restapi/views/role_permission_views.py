
    

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from restapi.models import RolePermission, Role


class RolePermissionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["Role Permission"])
    def get(self, request, role_id):

        role = Role.objects.filter(id=role_id).first()

        if not role:
            return Response({
                "success": False,
                "message": "Role not found"
            }, status=404)

        permissions = RolePermission.objects.filter(role=role)

        data = []
        for perm in permissions:
            data.append({
                "id": perm.id,
                "module": perm.module_key,
                "category": perm.category_key,
                "subcategory": perm.subcategory_key,
                "can_view": perm.can_view,
                "can_add": perm.can_add,
                "can_edit": perm.can_edit,
                "can_print": perm.can_print,
            })

        return Response({
            "success": True,
            "data": data
        })
    



class RolePermissionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Role Permission"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["role_id", "module", "category"],
            properties={
                "role_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "module": openapi.Schema(type=openapi.TYPE_STRING),
                "category": openapi.Schema(type=openapi.TYPE_STRING),
                "subcategory": openapi.Schema(type=openapi.TYPE_STRING),
                "can_view": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "can_add": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "can_edit": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "can_print": openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        )
    )
    def post(self, request):

        user = request.user

        # 🔐 ONLY SUPER ADMIN
        if user.profile.role.name.lower() != "super admin":
            return Response({
                "success": False,
                "message": "Only Super Admin can create permissions"
            }, status=403)

        role = Role.objects.filter(id=request.data.get("role_id")).first()

        if not role:
            return Response({
                "success": False,
                "message": "Role not found"
            }, status=404)

        perm = RolePermission.objects.create(
            role=role,
            module_key=request.data.get("module"),
            category_key=request.data.get("category"),
            subcategory_key=request.data.get("subcategory"),
            can_view=request.data.get("can_view", False),
            can_add=request.data.get("can_add", False),
            can_edit=request.data.get("can_edit", False),
            can_print=request.data.get("can_print", False),
        )

        return Response({
            "success": True,
            "message": "Permission created successfully",
            "data": {"id": perm.id}
        }, status=201)
    

class RolePermissionUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["Role Permission"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "can_view": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "can_add": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "can_edit": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "can_print": openapi.Schema(type=openapi.TYPE_BOOLEAN),
            }
        )
    )
    def patch(self, request, pk):

        user = request.user

        # 🔐 ONLY SUPER ADMIN
        if user.profile.role.name.lower() != "super admin":
            return Response({
                "success": False,
                "message": "Only Super Admin can update permissions"
            }, status=403)

        perm = RolePermission.objects.filter(id=pk).first()

        if not perm:
            return Response({
                "success": False,
                "message": "Permission not found"
            }, status=404)

        perm.can_view = request.data.get("can_view", perm.can_view)
        perm.can_add = request.data.get("can_add", perm.can_add)
        perm.can_edit = request.data.get("can_edit", perm.can_edit)
        perm.can_print = request.data.get("can_print", perm.can_print)

        perm.save()

        return Response({
            "success": True,
            "message": "Permission updated successfully"
        })