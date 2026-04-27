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
from restapi.models.role import Role
from restapi.services.permission_service import get_user_permissions
from restapi.models.clinic import Clinic
from django.contrib.auth.models import User
from restapi.models.user_profile import UserProfile
from datetime import datetime, timedelta, timezone
import jwt

class LoginProxyAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

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

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # External login
            resp = requests.post(
                settings.STAGE_LOGIN_URL,
                json={"username": username, "password": password},
                timeout=10
            )

            data = resp.json()

            # Always validate BEFORE DB writes
            if resp.status_code != 200:
                return Response(data, status=resp.status_code)

            # Create / update local user
            username = data.get("username")
            email = data.get("email")

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email or "",
                    "first_name": data.get("first_name") or "",
                    "last_name": data.get("last_name") or "",
                    "is_active": True,
                },
            )

            # Sync on re-login
            if not created:
                user.email = email or user.email
                user.first_name = data.get("first_name") or user.first_name
                user.last_name = data.get("last_name") or user.last_name
                user.save(update_fields=["email", "first_name", "last_name"])

            # Role mapping (single clean block)
            role_name = data.get("designation") or "User"
            role = Role.objects.filter(name__iexact=role_name).first()
            if not role:
                role = Role.objects.filter(name="User").first()

            # Profile setup (role + clinic)
            profile, _ = UserProfile.objects.get_or_create(user=user)

            clinic = Clinic.objects.order_by("id").first()  # dynamic, no hardcode

            profile.role = role
            profile.clinic = clinic
            profile.save(update_fields=["role", "clinic"])

            # Permissions
            permissions = get_user_permissions(
                type("obj", (), {"profile": type("p", (), {"role": role})()})()
            )

            # Generate INT token
            access_token, expires_at = self._build_access_token(user)
            refresh_token, refresh_expires_at = self._build_refresh_token(user)
            # int_access = str(refresh.access_token)
            # int_refresh = str(refresh)

            # Return unified response
            return Response(
                {
                    "success": True,
                    "message": "Login successful",
                    "data": {
                        "access_token": access_token,          # INT token
                        "refresh_token": refresh_token,
                        "ext_token": data.get("access"),       # EXT token
                        "token_type": "Bearer",

                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "email": user.email,
                            "designation": data.get("designation"),
                        },

                        "role": role.name if role else "User",
                        "permissions": permissions,
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

            # Resolve role
            role_name = data.get("designation") or "User"

            role = Role.objects.filter(name__iexact=role_name).first()
            if not role:
                role = Role.objects.filter(name="User").first()

            # Get DB permissions
            permissions = get_user_permissions(
                type("obj", (), {"profile": type("p", (), {"role": role})()})()
            )

            clinic = Clinic.objects.order_by("id").first()

            clinic_data = {
                "id": clinic.id,
                "name": clinic.name,
            } if clinic else None

            return Response(
                {
                    "success": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "data": {
                        **data,

                        "clinic": clinic_data,

                        "clinics": [
                            {
                                "clinic_id": clinic_data["id"],
                                "clinic__name": clinic_data["name"],
                                "is_default": True,
                            }
                        ] if clinic_data else [],

                        "role": {
                            "name": role.name
                        },
                        "permissions": permissions,
                    },
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

            if not token:
                return Response({"error": "Authorization token missing"}, status=401)

            auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"

            params = {
                "limit": request.query_params.get("limit", 10),
                "offset": request.query_params.get("offset", 0),
                "search": request.query_params.get("search", ""),
            }

            resp = requests.get(
                settings.STAGE_USERS_URL,
                headers={"Authorization": auth_header},
                params=params,
                timeout=10,
            )

            # ✅ SAFE JSON HANDLING (THIS FIXES YOUR 500)
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
                        "url": settings.STAGE_USERS_URL,
                        "params": params,
                        "auth": auth_header[:20] + "...",
                    },
                },
                status=resp.status_code,
            )

        except requests.exceptions.Timeout:
            return Response({"error": "Users service timeout"}, status=504)

        except Exception as e:
            return Response({"error": "Users fetch failed", "details": str(e)}, status=500)