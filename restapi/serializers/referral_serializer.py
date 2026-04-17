from rest_framework import serializers
from restapi.models.referral import ReferralSource


class ReferralSourceSerializer(serializers.ModelSerializer):

    # =============================
    # 🔥 REFERRAL DEPARTMENT
    # =============================
    referral_department_id = serializers.SerializerMethodField()
    referral_department_name = serializers.SerializerMethodField()

    # =============================
    # 🔥 EXTERNAL CLINIC
    # =============================
    external_clinic_id = serializers.SerializerMethodField()
    external_clinic_name = serializers.SerializerMethodField()

    # =============================
    # 🔥 COUNT
    # =============================
    referral_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReferralSource
        fields = [
            "id",
            "name",
            "email",
            "phone",

            "referral_department_id",
            "referral_department_name",

            "external_clinic_id",
            "external_clinic_name",

            "referral_count",
        ]

    # =============================
    # METHODS
    # =============================
    def get_referral_department_id(self, obj):
        return obj.referral_department.id if obj.referral_department else None

    def get_referral_department_name(self, obj):
        return obj.referral_department.name if obj.referral_department else None

    def get_external_clinic_id(self, obj):
        return obj.external_clinic.id if obj.external_clinic else None

    def get_external_clinic_name(self, obj):
        return obj.external_clinic.name if obj.external_clinic else None