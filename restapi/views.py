from rest_framework import generics
from .models import Clinic
from .serializers import ClinicSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ClinicReadSerializer

class ClinicCreateAPIView(generics.CreateAPIView):
    queryset = Clinic.objects.all()
    serializer_class = ClinicSerializer

class ClinicRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    queryset = Clinic.objects.all()
    serializer_class = ClinicSerializer
    lookup_field = 'id'

class GetClinicView(APIView):

    def get(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            return Response(
                {"error": "Clinic not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ClinicReadSerializer(clinic)
        return Response(serializer.data, status=status.HTTP_200_OK)
