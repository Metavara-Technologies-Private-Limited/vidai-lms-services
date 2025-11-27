from django.urls import path
from .views import ClinicCreateAPIView, ClinicRetrieveUpdateAPIView, GetClinicView

urlpatterns = [
    path('clinics', ClinicCreateAPIView.as_view(), name='clinic-create'),
    path('clinics/<int:id>/', ClinicRetrieveUpdateAPIView.as_view(), name='clinic-detail'),
    path('get_clinic/<int:clinic_id>/', GetClinicView.as_view())
]
