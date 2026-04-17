# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import requests

from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed

from restapi.serializers.user_serializer import UserSerializer
from restapi.utils.jwt_authentication import JWTAuthentication


class LoginProxyAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            resp = requests.post(
                settings.STAGE_LOGIN_URL,
                json={
                    "username": username,
                    "password": password
                },
                timeout=10
            )

            data = resp.json()

            # Pass through error from external API
            if resp.status_code != 200:
                return Response(data, status=resp.status_code)

            # Return only required data
            return Response(
                {
                    "token": data.get("access"),
                    "user": {
                        "username": data.get("username"),
                        "first_name": data.get("first_name"),
                        "last_name": data.get("last_name"),
                        "email": data.get("email"),
                        "designation": data.get("designation"),
                    }
                },
                status=status.HTTP_200_OK
            )

        except requests.exceptions.Timeout:
            return Response(
                {"error": "Login service timeout"},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )

        except Exception as e:
            return Response(
                {"error": "Login failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProfileProxyAPIView(APIView):
    authentication_classes = []  # ✅ don't decode token — just forward it
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.headers.get("Authorization")

        if not token:
            return Response(
                {
                    "error": "Authorization token missing",
                    "debug": {
                        "received_headers": dict(request.headers),
                    },
                },
                status=401,
            )

        try:
            try:
                local_auth = JWTAuthentication().authenticate(request)
            except AuthenticationFailed:
                local_auth = None

            if local_auth:
                user, _ = local_auth
                request.user = user
                return Response(
                    {
                        "success": True,
                        "status_code": 200,
                        "data": UserSerializer(
                            user,
                            context={"request": request},
                        ).data,
                    },
                    status=status.HTTP_200_OK,
                )

            auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"

            resp = requests.get(
                settings.STAGE_PROFILE_URL,
                headers={"Authorization": auth_header},
                timeout=10,
            )

            # Safe JSON parse
            try:
                data = resp.json() if resp.content else {}
            except Exception:
                data = {"raw": resp.text}

            return Response(
                {
                    "success": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "data": data,
                    "debug": {
                        "upstream_url": settings.STAGE_PROFILE_URL,
                        "sent_auth_header": auth_header[:20] + "...",
                    },
                },
                status=resp.status_code,
            )

        except requests.exceptions.Timeout:
            return Response(
                {
                    "error": "Profile service timeout",
                    "debug": {
                        "upstream_url": settings.STAGE_PROFILE_URL,
                        "timeout": 10,
                    },
                },
                status=504,
            )

        except requests.exceptions.RequestException as e:
            return Response(
                {
                    "error": "Upstream request failed",
                    "details": str(e),
                },
                status=502,
            )

        except Exception as e:
            return Response(
                {
                    "error": "Internal server error",
                    "details": str(e),
                },
                status=500,
            )


class UsersProxyAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            token = request.headers.get("Authorization")

            params = {
                "limit": request.query_params.get("limit", 10),
                "offset": request.query_params.get("offset", 0),
                "search": request.query_params.get("search", ""),
            }

            resp = requests.get(
                settings.STAGE_USERS_URL,
                headers={
                    "Authorization": token,
                },
                params=params,
                timeout=10,
            )

            return Response(resp.json(), status=resp.status_code)

        except requests.exceptions.Timeout:
            return Response(
                {"error": "Users service timeout"},
                status=504
            )

        except Exception as e:
            return Response(
                {"error": "Users fetch failed", "details": str(e)},
                status=500
            )
