from django.test import TestCase

from restapi.models import Clinic, Department, Lead
from restapi.models.reputation import ReviewRequest, ReviewRequestLead


class ReputationPublicReviewLinkTests(TestCase):
    def setUp(self):
        self.clinic = Clinic.objects.create(
            name="Apollo Fertility",
            email="admin@apollo.test",
        )
        self.department = Department.objects.create(
            name="IVF",
            clinic=self.clinic,
        )
        self.lead = Lead.objects.create(
            clinic=self.clinic,
            department=self.department,
            full_name="Test Lead",
            contact_no="9999999999",
            source="website",
            treatment_interest="IVF",
        )
        self.review_request = ReviewRequest.objects.create(
            clinic=self.clinic,
            request_name="Post Visit Feedback",
            description="Please share your feedback",
            collect_on="form",
            mode="email",
            status="sent",
        )
        ReviewRequestLead.objects.create(
            review_request=self.review_request,
            lead=self.lead,
            request_sent=True,
            review_submitted=False,
        )

    def test_public_review_request_detail_resolves_for_valid_lead(self):
        response = self.client.get(
            f"/api/reputation/public/requests/{self.review_request.id}/",
            {"lead": str(self.lead.id)},
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["data"]["id"], str(self.review_request.id))
        self.assertEqual(payload["data"]["lead_id"], str(self.lead.id))
        self.assertEqual(payload["data"]["lead_name"], self.lead.full_name)
        self.assertFalse(payload["data"]["review_submitted"])
