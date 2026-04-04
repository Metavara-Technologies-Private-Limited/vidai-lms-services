from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

# ❌ OLD REMOVE
# from restapi.utils.permissions import has_permission

# ✅ NEW ADD
from restapi.utils.permissions import secure_endpoint, CAN_VIEW, CAN_ADD, CAN_EDIT
from restapi.utils.tenant import filter_by_clinic

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.serializers.user_serializer import UserSerializer
from restapi.services import get_user_permissions


# =========================
# CREATE USER
# =========================
class UserCreateAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        request_body=UserSerializer,
        responses={201: UserSerializer}
    )
    def post(self, request):
        serializer = UserSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "success": True,
                "message": "User created successfully",
                "data": UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )



# =========================
# LIST USERS
# =========================
class UserListAPIView(APIView):

    @swagger_auto_schema(tags=["User"])
    @secure_endpoint("users", CAN_VIEW)
    def get(self, request):

        users = User.objects.select_related(
            "profile", "profile__role", "profile__clinic"
        ).all()

        users = filter_by_clinic(users, request.user)

        return Response({
            "success": True,
            "data": UserSerializer(users, many=True).data
        })



# =========================
# USER DETAIL
# =========================
class UserDetailAPIView(APIView):

    @swagger_auto_schema(tags=["User"])
    @secure_endpoint("users", CAN_VIEW)
    def get(self, request, pk):

        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role", "profile__clinic"),
            id=pk
        )

        # ✅ OBJECT SECURITY FIX
        if request.user.profile.role.name.lower() != "super admin":
            if user.profile.clinic != request.user.profile.clinic:
                return Response({"message": "Not allowed"}, status=403)

        return Response({
            "success": True,
            "data": UserSerializer(user).data
        })



# =========================
# UPDATE USER (PUT)
# =========================
class UserUpdateAPIView(APIView):

    @secure_endpoint("users", CAN_EDIT)
    def put(self, request, pk):

        user = get_object_or_404(User, id=pk)

        serializer = UserSerializer(
            user,
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response({
            "success": True,
            "data": UserSerializer(user).data
        })


# =========================
# PARTIAL UPDATE USER (PATCH)
# =========================
class UserPartialUpdateAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        request_body=UserSerializer
    )
    @secure_endpoint("users", CAN_EDIT)   # ✅ ADDED
    def patch(self, request, pk):

        user = get_object_or_404(User, id=pk)

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
            "data": UserSerializer(user).data
        })


# =========================
# UPDATE USER STATUS
# =========================
class UserStatusUpdateAPIView(APIView):

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
    @secure_endpoint("users", CAN_EDIT)   # ✅ ADDED
    def patch(self, request, pk):

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

        profile = getattr(user, "profile", None)
        if not profile:
            return Response({
                "success": False,
                "message": "User profile not found"
            }, status=status.HTTP_404_NOT_FOUND)

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

    @swagger_auto_schema(tags=["User"])
    @secure_endpoint("users", CAN_EDIT)   # ✅ ADDED
    def delete(self, request, pk):

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