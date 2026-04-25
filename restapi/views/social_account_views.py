from rest_framework.response import Response
from rest_framework.views import APIView
from restapi.models.social_account import SocialAccount
from rest_framework.exceptions import ValidationError

from restapi.utils.clinic_scope import resolve_request_clinic

class SocialAccountListAPIView(APIView):
    def get(self, request, clinic_id):
        clinic = resolve_request_clinic(request, required=True)
        if int(clinic_id) != clinic.id:
            raise ValidationError({"clinic_id": "Clinic access denied"})

        accounts = SocialAccount.objects.filter(
            clinic_id=clinic_id, is_active=True
        ).values("platform", "page_name", "page_id", "customer_id")  # ← added customer_id

        return Response(list(accounts))