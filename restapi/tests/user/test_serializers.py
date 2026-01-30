from django.test import TestCase
from rest_framework.exceptions import ValidationError
from restapi.serializers import UserCreateSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class UserCreateSerializerTest(TestCase):

    def test_user_create_success(self):
        payload = {
            "username": "newuser",
            "password": "secret123"
        }

        serializer = UserCreateSerializer(data=payload)
        self.assertTrue(serializer.is_valid())

        user = serializer.save()
        self.assertTrue(user.check_password("secret123"))

    def test_duplicate_username_fails(self):
        User.objects.create_user(username="dup", password="x")

        serializer = UserCreateSerializer(
            data={"username": "dup", "password": "y"}
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
