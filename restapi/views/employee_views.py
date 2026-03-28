
# =====================================================
# Imports
# =====================================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from restapi.models import Employee
from restapi.serializers.employee import (
    EmployeeCreateSerializer,
    EmployeeReadSerializer,
    EmployeeUpdateSerializer,
    UserCreateSerializer,
)



# -------------------------------------------------------------------
# User Create API View (POST)
# -------------------------------------------------------------------
class UserCreateAPIView(APIView):

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "username": user.username
            },
            status=status.HTTP_201_CREATED
        )



# -------------------------------------------------------------------
# Employee Create API View (POST)
# -------------------------------------------------------------------
class EmployeeCreateAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Create Employee",
        operation_description="Create an employee under a clinic and department",
        request_body=EmployeeCreateSerializer,
        responses={
            201: EmployeeReadSerializer,
            400: "Validation Error",
            401: "Unauthorized"
        },
        tags=["Employee"]
    )
    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            EmployeeReadSerializer(employee).data,
            status=status.HTTP_201_CREATED
        )

class EmployeeUpdateAPIView(APIView):

    @swagger_auto_schema(
        operation_summary="Update Employee",
        operation_description="Update an existing employee's details (email, contact, type, etc.)",
        request_body=EmployeeUpdateSerializer,
        responses={
            200: EmployeeReadSerializer,
            400: "Validation Error",
            404: "Employee not found",
        },
        tags=["Employee"]
    )
    def put(self, request, employee_id):
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeUpdateSerializer(
            employee,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_employee = serializer.save()

        return Response(
            EmployeeReadSerializer(updated_employee).data,
            status=status.HTTP_200_OK,
        )
