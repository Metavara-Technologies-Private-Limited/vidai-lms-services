# restapi/serializers/referral_serializer.py

from rest_framework import serializers
from restapi.models.referral import ReferralSource


class ReferralSourceSerializer(serializers.ModelSerializer):
    clinic_name = serializers.CharField(source="external_clinic.name", read_only=True)
    referral_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReferralSource
        fields = [
            "id",
            "name",
            "type",
            "email",
            "phone",
            "clinic_name",      # external clinic
            "referral_count"
        ]