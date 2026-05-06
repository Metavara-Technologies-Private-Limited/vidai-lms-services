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

        accounts = SocialAccount.objects.filter(clinic_id=clinic_id, is_active=True)

        result = []

        for acc in accounts:
            data = {
                "platform": acc.platform,
                "page_name": acc.page_name,
                "page_id": acc.page_id,
                "customer_id": acc.customer_id,
                "account_id": acc.account_id,
                "instagram_user_id": acc.org_urn,
            }

            if acc.platform == "facebook":
                data["connected"] = bool(acc.page_id and acc.account_id)
                data["instagram_connected"] = bool(acc.org_urn)

            elif acc.platform == "google":
                data["connected"] = bool(acc.customer_id)

            elif acc.platform == "linkedin":
                data["connected"] = bool(acc.account_id and acc.org_urn)

            else:
                data["connected"] = True

            result.append(data)

        return Response(result)
