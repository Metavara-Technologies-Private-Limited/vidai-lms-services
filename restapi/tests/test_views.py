from rest_framework.test import APITestCase
from rest_framework import status
from restapi.models import Clinic, Department, Equipments


class FullAPITestSuite(APITestCase):
    """
    This test class covers ALL APIs in views.py.
    These are API-level unit tests, which means:
    - views.py is tested
    - serializers.py is tested automatically
    - models.py is tested automatically
    - real DB is NOT used (test DB only)
    """

    def setUp(self):
        """
        setUp() runs BEFORE EACH test case.

        Here we create basic data that is required
        for most APIs:
        - one Clinic
        - one Department under that Clinic
        """

        self.clinic = Clinic.objects.create(
            name="Test Clinic"
        )

        self.department = Department.objects.create(
            clinic=self.clinic,
            name="Radiology",
            is_active=True
        )

    # ==================================================
    # CLINIC MODULE TEST CASES
    # ==================================================

    def test_create_clinic_success(self):
        """
        SUCCESS CASE:
        - Tests POST /api/clinics
        - Valid payload
        - Expected result: 201 CREATED
        """

        response = self.client.post(
            "/api/clinics",
            {
                "name": "Apollo Clinic",
                "department": []
            },
            format="json"
        )

        # Check API response status
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_clinic_missing_name(self):
        """
        ERROR CASE:
        - Tests POST /api/clinics
        - 'name' field is missing
        - Serializer should fail
        - Expected result: 400 BAD REQUEST
        """

        response = self.client.post(
            "/api/clinics",
            {"department": []},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_clinic_success(self):
        """
        SUCCESS CASE:
        - Tests GET /api/get_clinic/<clinic_id>/
        - Clinic exists
        - Expected result: 200 OK
        """

        response = self.client.get(
            f"/api/get_clinic/{self.clinic.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_clinic_invalid_id(self):
        """
        ERROR CASE:
        - Tests GET /api/get_clinic/<invalid_id>/
        - Clinic does not exist
        - Expected result: 404 NOT FOUND
        """

        response = self.client.get("/api/get_clinic/9999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_clinic_success(self):
        """
        SUCCESS CASE:
        - Tests PUT /api/clinics/<clinic_id>/
        - Clinic exists
        - Expected result: 200 OK
        """

        response = self.client.put(
            f"/api/clinics/{self.clinic.id}/",
            {
                "name": "Updated Clinic",
                "department": []
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_clinic_invalid_id(self):
        """
        ERROR CASE:
        - Tests PUT /api/clinics/<invalid_id>/
        - Clinic does not exist
        - Expected result: 404 NOT FOUND
        """

        response = self.client.put(
            "/api/clinics/9999/",
            {
                "name": "Invalid Clinic",
                "department": []
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================================================
    # EQUIPMENT MODULE TEST CASES
    # ==================================================

    def test_create_equipment_success(self):
        """
        SUCCESS CASE:
        - Tests POST /api/departments/<department_id>/equipments/
        - Department exists
        - Expected result: 201 CREATED
        """

        response = self.client.post(
            f"/api/departments/{self.department.id}/equipments/",
            {
                "equipment_name": "CT Scanner",
                "is_active": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_equipment_invalid_department(self):
        """
        ERROR CASE:
        - Tests POST /api/departments/<invalid_id>/equipments/
        - Department does not exist
        - Expected result: 404 NOT FOUND
        """

        response = self.client.post(
            "/api/departments/9999/equipments/",
            {"equipment_name": "CT"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_equipment_success(self):
        """
        SUCCESS CASE:
        - Tests PUT /api/departments/<department_id>/equipments/<equipment_id>/
        - Equipment exists
        - Expected result: 200 OK
        """

        equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="MRI",
            is_active=True
        )

        response = self.client.put(
            f"/api/departments/{self.department.id}/equipments/{equipment.id}/",
            {
                "equipment_name": "MRI Updated",
                "is_active": True
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_equipment_invalid_id(self):
        """
        ERROR CASE:
        - Tests PUT /api/departments/<department_id>/equipments/<invalid_id>/
        - Equipment does not exist
        - Expected result: 404 NOT FOUND
        """

        response = self.client.put(
            f"/api/departments/{self.department.id}/equipments/9999/",
            {"equipment_name": "Invalid"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_inactivate_equipment_success(self):
        """
        SUCCESS CASE:
        - Tests PATCH /inactive/
        - Equipment exists
        - Expected result:
            * 200 OK
            * equipment.is_active becomes False
        """

        equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="XRay",
            is_active=True
        )

        response = self.client.patch(
            f"/api/departments/{self.department.id}/equipments/{equipment.id}/inactive/"
        )

        equipment.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(equipment.is_active)

    def test_inactivate_equipment_invalid_id(self):
        """
        ERROR CASE:
        - Tests PATCH /inactive/ with invalid equipment ID
        - Expected result: 404 NOT FOUND
        """

        response = self.client.patch(
            f"/api/departments/{self.department.id}/equipments/9999/inactive/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_equipment_success(self):
        """
        SUCCESS CASE:
        - Tests PATCH /delete/
        - Equipment exists
        - Expected result:
            * equipment.is_deleted = True
            * equipment.is_active = False
        """

        equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="Ultrasound",
            is_active=True,
            is_deleted=False
        )

        response = self.client.patch(
            f"/api/departments/{self.department.id}/equipments/{equipment.id}/delete/"
        )

        equipment.refresh_from_db()

        self.assertTrue(equipment.is_deleted)
        self.assertFalse(equipment.is_active)

    def test_soft_delete_equipment_invalid_id(self):
        """
        ERROR CASE:
        - Tests PATCH /delete/ with invalid equipment ID
        - Expected result: 404 NOT FOUND
        """

        response = self.client.patch(
            f"/api/departments/{self.department.id}/equipments/9999/delete/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_soft_delete_via_delete_method(self):
        """
        SUCCESS CASE:
        - Tests DELETE method
        - DELETE internally calls PATCH logic
        """

        equipment = Equipments.objects.create(
            dep=self.department,
            equipment_name="ECG",
            is_active=True,
            is_deleted=False
        )

        response = self.client.delete(
            f"/api/departments/{self.department.id}/equipments/{equipment.id}/delete/"
        )

        equipment.refresh_from_db()

        self.assertTrue(equipment.is_deleted)
