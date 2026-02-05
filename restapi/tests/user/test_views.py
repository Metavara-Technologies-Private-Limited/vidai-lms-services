from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status


class UserCreateAPIViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_user_create_api_success(self):
        response = self.client.post(
            "/api/users/",
            {
                "username": "apiuser",
                "password": "pass123"
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
