from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.serializers.user_serializer import UserSerializer


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
        serializer = UserSerializer(data=request.data)
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

    @swagger_auto_schema(
        tags=["User"],
        responses={200: UserSerializer(many=True)}
    )
    def get(self, request):
        users = User.objects.select_related("profile", "profile__role").all()

        return Response(
            {
                "success": True,
                "message": "Users fetched successfully",
                "data": UserSerializer(users, many=True).data
            }
        )


# =========================
# RETRIEVE USER
# =========================
class UserDetailAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        responses={200: UserSerializer}
    )
    def get(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role"),
            id=pk
        )

        return Response(
            {
                "success": True,
                "message": "User fetched successfully",
                "data": UserSerializer(user).data
            }
        )


# =========================
# UPDATE USER (FULL)
# =========================
class UserUpdateAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        request_body=UserSerializer,
        responses={200: UserSerializer}
    )
    def put(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role"),
            id=pk
        )

        serializer = UserSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "success": True,
                "message": "User updated successfully",
                "data": UserSerializer(user).data
            }
        )


# =========================
# PARTIAL UPDATE USER (PATCH)
# =========================
class UserPartialUpdateAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        request_body=UserSerializer,
        responses={200: UserSerializer}
    )
    def patch(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__role"),
            id=pk
        )

        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "success": True,
                "message": "User updated successfully",
                "data": UserSerializer(user).data
            }
        )


# =========================
# UPDATE USER STATUS ONLY
# =========================
class UserStatusUpdateAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "is_active": openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        ),
        responses={200: "Status updated"}
    )
    def patch(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile"),
            id=pk
        )

        is_active = request.data.get("is_active")

        if is_active is None:
            return Response(
                {
                    "success": False,
                    "message": "is_active field is required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        profile = getattr(user, "profile", None)
        if not profile:
            return Response(
                {
                    "success": False,
                    "message": "User profile not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        profile.is_active = is_active
        profile.save()

        return Response(
            {
                "success": True,
                "message": "User status updated successfully"
            }
        )


# =========================
# DELETE USER
# =========================
class UserDeleteAPIView(APIView):

    @swagger_auto_schema(
        tags=["User"],
        responses={204: "Deleted successfully"}
    )
    def delete(self, request, pk):
        user = get_object_or_404(User, id=pk)

        user.delete()

        return Response(
            {
                "success": True,
                "message": "User deleted successfully"
            },
            status=status.HTTP_204_NO_CONTENT
        )