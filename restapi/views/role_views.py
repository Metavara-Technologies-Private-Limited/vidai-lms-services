from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from drf_yasg.utils import swagger_auto_schema

from restapi.models import Role
from restapi.serializers.role_serializer import (
    RoleSerializer,
    RoleReadSerializer
)


# =========================
# CREATE ROLE
# =========================
class RoleCreateAPIView(APIView):

    @swagger_auto_schema(
        tags=["Role"],
        request_body=RoleSerializer,
        responses={201: RoleReadSerializer}
    )
    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.save()

        return Response(
            {
                "success": True,
                "message": "Role created successfully",
                "data": RoleReadSerializer(role).data
            },
            status=status.HTTP_201_CREATED
        )


# =========================
# LIST ROLES
# =========================
class RoleListAPIView(APIView):

    @swagger_auto_schema(
        tags=["Role"],
        responses={200: RoleReadSerializer(many=True)}
    )
    def get(self, request):
        roles = Role.objects.all()

        return Response(
            {
                "success": True,
                "message": "Roles fetched successfully",
                "data": RoleReadSerializer(roles, many=True).data
            }
        )


# =========================
# RETRIEVE ROLE
# =========================
class RoleDetailAPIView(APIView):

    @swagger_auto_schema(
        tags=["Role"],
        responses={200: RoleReadSerializer}
    )
    def get(self, request, pk):
        role = get_object_or_404(Role, id=pk)

        return Response(
            {
                "success": True,
                "message": "Role fetched successfully",
                "data": RoleReadSerializer(role).data
            }
        )


# =========================
# UPDATE ROLE
# =========================
class RoleUpdateAPIView(APIView):

    @swagger_auto_schema(
        tags=["Role"],
        request_body=RoleSerializer,
        responses={200: RoleReadSerializer}
    )
    def put(self, request, pk):
        role = get_object_or_404(Role, id=pk)

        serializer = RoleSerializer(role, data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.save()

        return Response(
            {
                "success": True,
                "message": "Role updated successfully",
                "data": RoleReadSerializer(role).data
            }
        )


# =========================
# DELETE ROLE
# =========================
class RoleDeleteAPIView(APIView):

    @swagger_auto_schema(
        tags=["Role"],
        responses={204: "Deleted successfully"}
    )
    def delete(self, request, pk):
        role = get_object_or_404(Role, id=pk)

        role.delete()

        return Response(
            {
                "success": True,
                "message": "Role deleted successfully"
            },
            status=status.HTTP_204_NO_CONTENT
        )