from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.services import get_user_permissions


class LoginAPIView(APIView):

    @swagger_auto_schema(
        tags=["Auth"],
        operation_summary="User Login",
        operation_description="Authenticate user and return role-based permissions",

        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["username", "password"],
            properties={
                "username": openapi.Schema(type=openapi.TYPE_STRING, example="superadmin"),
                "password": openapi.Schema(type=openapi.TYPE_STRING, example="Admin@123"),
            }
        ),

        responses={
            200: openapi.Response(
                description="Login Successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "user": openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "id": openapi.Schema(type=openapi.TYPE_INTEGER),
                                        "username": openapi.Schema(type=openapi.TYPE_STRING),
                                        "email": openapi.Schema(type=openapi.TYPE_STRING),
                                    }
                                ),
                                "role": openapi.Schema(type=openapi.TYPE_STRING),
                                "permissions": openapi.Schema(type=openapi.TYPE_OBJECT),
                            }
                        )
                    }
                )
            ),

            400: "User role not assigned",
            401: "Invalid credentials"
        }
    )
    def post(self, request):

        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {
                    "success": False,
                    "message": "Invalid credentials"
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not hasattr(user, "profile") or not user.profile.role:
            return Response(
                {
                    "success": False,
                    "message": "User role not assigned"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        permissions = get_user_permissions(user)

        return Response(
            {
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email
                    },
                    "role": user.profile.role.name,
                    "permissions": permissions
                }
            },
            status=status.HTTP_200_OK
        )