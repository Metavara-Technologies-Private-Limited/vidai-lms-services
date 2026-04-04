from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import User
import jwt


class JWTAuthentication(BaseAuthentication):

    def authenticate(self, request):

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        try:
            prefix, token = auth_header.split()
        except ValueError:
            raise AuthenticationFailed("Invalid token format")

        if prefix.lower() != "bearer":
            raise AuthenticationFailed("Invalid token prefix")

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token")

        user_id = payload.get("sub")

        if not user_id:
            raise AuthenticationFailed("Invalid token payload")

        user = User.objects.filter(id=user_id).first()

        if not user:
            raise AuthenticationFailed("User not found")

        return (user, None)