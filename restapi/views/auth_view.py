from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta, timezone
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from restapi.services import get_user_permissions


class LoginAPIView(APIView):

    def _build_access_token(self, user):
        ttl_minutes = int(getattr(settings, "JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        payload = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return token, expires_at

    def _build_refresh_token(self, user):
        ttl_days = int(getattr(settings, "JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7))
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        payload = {
            "sub": str(user.id),
            "type": "refresh",
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        return token, expires_at

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
                                "access_token": openapi.Schema(type=openapi.TYPE_STRING),
                                "refresh_token": openapi.Schema(type=openapi.TYPE_STRING),
                                "token_type": openapi.Schema(type=openapi.TYPE_STRING, example="Bearer"),
                                "expires_at": openapi.Schema(type=openapi.TYPE_STRING, example="2026-04-05T10:00:00+00:00"),
                                "refresh_expires_at": openapi.Schema(type=openapi.TYPE_STRING, example="2026-04-12T10:00:00+00:00"),
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
        access_token, expires_at = self._build_access_token(user)
        refresh_token, refresh_expires_at = self._build_refresh_token(user)

        return Response(
            {
                "success": True,
                "message": "Login successful",
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_at": expires_at.isoformat(),
                    "refresh_expires_at": refresh_expires_at.isoformat(),
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


class TokenRefreshAPIView(APIView):

    @swagger_auto_schema(
        tags=["Auth"],
        operation_summary="Refresh Access Token",
        operation_description="Generate a new access token using a valid refresh token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["refresh_token"],
            properties={
                "refresh_token": openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        responses={
            200: openapi.Response(
                description="Token refreshed",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "access_token": openapi.Schema(type=openapi.TYPE_STRING),
                                "token_type": openapi.Schema(type=openapi.TYPE_STRING, example="Bearer"),
                                "expires_at": openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                    }
                )
            ),
            400: "refresh_token is required",
            401: "Invalid or expired refresh token",
        },
    )
    def post(self, request):
        refresh_token = request.data.get("refresh_token")

        if not refresh_token:
            return Response(
                {"success": False, "message": "refresh_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=["HS256"])
        except ExpiredSignatureError:
            return Response(
                {"success": False, "message": "Refresh token expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except InvalidTokenError:
            return Response(
                {"success": False, "message": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if payload.get("type") != "refresh":
            return Response(
                {"success": False, "message": "Invalid refresh token type"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = payload.get("sub")
        user = None
        if user_id:
            from django.contrib.auth.models import User
            user = User.objects.filter(id=user_id).first()

        if not user:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ttl_minutes = int(getattr(settings, "JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        access_payload = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }
        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm="HS256")

        return Response(
            {
                "success": True,
                "message": "Token refreshed successfully",
                "data": {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_at": expires_at.isoformat(),
                },
            },
            status=status.HTTP_200_OK,
        )