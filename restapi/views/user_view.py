from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.serializers.user_serializer import UserSerializer
from restapi.services import get_user_permissions
from restapi.utils.permissions import (
    has_action_permission_for_labels,
    is_super_admin_role
)


def _has_users_permission(user, action: str) -> bool:
    return has_action_permission_for_labels(
        user,
        action,
        ["users", "user", "user management", "user_management"],
    )


def _permission_denied(action: str):
    return Response(
        {
            "success": False,
            "message": f"Permission denied: users {action}",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _can_access_user_record(request_user, target_user, action: str) -> bool:
    if request_user.id == target_user.id and action in {"view", "edit"}:
        return True
    return _has_users_permission(request_user, action)


# =========================
# CREATE USER
# =========================
class UserCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(tags=["User"], request_body=UserSerializer)
    def post(self, request):
        if not _has_users_permission(request.user, "add"):
            return _permission_denied("add")

        serializer = UserSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response({
            "success": True,
            "message": "User created successfully",
            "data": UserSerializer(user, context={"request": request}).data
        }, status=status.HTTP_201_CREATED)


# =========================
# LIST USERS (FIXED)
# =========================
class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["User"])
    def get(self, request):
        if not _has_users_permission(request.user, "view"):
            return _permission_denied("view")

        # Base query: all active users with profile.
        users = User.objects.filter(
            profile__isnull=False,
            profile__is_active=True,
        ).select_related(
            "profile",
            "profile__role",
            "profile__clinic"
        )

        user = request.user

        if hasattr(user, "profile") and user.profile and user.profile.role:

            # Super Admin can view all users across clinics.
            if is_super_admin_role(user.profile.role):
                pass
            else:
                # Non-super-admin users can view only users from their clinic.
                users = users.filter(
                    profile__clinic=user.profile.clinic
                )

        users = users.distinct()

        return Response({
            "success": True,
            "message": "Users fetched successfully",
            "data": UserSerializer(
                users,
                many=True,
                context={"request": request}
            ).data
        }, status=status.HTTP_200_OK)


# =========================
# RETRIEVE USER
# =========================
class UserDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["User"])
    def get(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role"),
            id=pk
        )

        if not _can_access_user_record(request.user, user, "view"):
            return _permission_denied("view")

        return Response({
            "success": True,
            "message": "User fetched successfully",
            "data": UserSerializer(user, context={"request": request}).data
        })


# =========================
# UPDATE USER
# =========================
class UserUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(tags=["User"], request_body=UserSerializer)
    def put(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role"),
            id=pk,
        )

        if not _can_access_user_record(request.user, user, "edit"):
            return _permission_denied("edit")

        serializer = UserSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response({
            "success": True,
            "message": "User updated successfully",
            "data": UserSerializer(user, context={"request": request}).data
        })


# =========================
# PARTIAL UPDATE USER
# =========================
class UserPartialUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(tags=["User"], request_body=UserSerializer)
    def patch(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role"),
            id=pk,
        )

        if not _can_access_user_record(request.user, user, "edit"):
            return _permission_denied("edit")

        serializer = UserSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response({
            "success": True,
            "message": "User updated successfully",
            "data": UserSerializer(user, context={"request": request}).data
        })


# =========================
# UPDATE USER STATUS
# =========================
class UserStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=["User"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["is_active"],
            properties={
                "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        )
    )
    def patch(self, request, pk):
        if not _has_users_permission(request.user, "edit"):
            return _permission_denied("edit")

        user = get_object_or_404(
            User.objects.select_related("profile"),
            id=pk
        )

        is_active = request.data.get("is_active")

        if is_active is None:
            return Response({
                "success": False,
                "message": "is_active field is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        profile = user.profile
        profile.is_active = is_active
        profile.save()

        return Response({
            "success": True,
            "message": "User status updated successfully"
        })


# =========================
# DELETE USER
# =========================
class UserDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["User"])
    def delete(self, request, pk):
        if not _has_users_permission(request.user, "print"):
            return _permission_denied("print")

        user = get_object_or_404(User, id=pk)
        user.delete()

        return Response({
            "success": True,
            "message": "User deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)


# =========================
# USER PERMISSIONS API
# =========================
class UserPermissionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["User"])
    def get(self, request):
        permissions = get_user_permissions(request.user)

        return Response({
            "success": True,
            "message": "Permissions fetched successfully",
            "data": {
                "role": request.user.profile.role.name if request.user.profile.role else None,
                "permissions": permissions
            }
        })


# =========================
# PROFILE PHOTO UPDATE
# =========================
class MyProfilePhotoAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(tags=["User"], request_body=UserSerializer)
    def patch(self, request):
        serializer = UserSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "success": True,
            "message": "Profile photo updated successfully",
            "data": UserSerializer(user, context={"request": request}).data
        })