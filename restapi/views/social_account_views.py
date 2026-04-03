from rest_framework.response import Response
from rest_framework.views import APIView
from restapi.models.social_account import SocialAccount

class SocialAccountListAPIView(APIView):
    def get(self, request, clinic_id):
        accounts = SocialAccount.objects.filter(
            clinic_id=clinic_id, is_active=True
        ).values("platform", "page_name", "page_id")

        return Response(list(accounts))
