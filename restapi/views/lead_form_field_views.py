from django.utils.text import slugify
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from restapi.models import LeadFormField
from restapi.serializers.lead_form_field_serializer import LeadFormFieldSerializer


def _build_field_key(label):
    base = slugify(label or "custom-field").replace("-", "_") or "custom_field"
    field_key = base
    suffix = 2
    while LeadFormField.objects.filter(field_key=field_key).exists():
        field_key = f"{base}_{suffix}"
        suffix += 1
    return field_key


class LeadFormFieldListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fields = LeadFormField.objects.filter(is_active=True).order_by("sort_order", "field_label")
        return Response(LeadFormFieldSerializer(fields, many=True).data)

    def post(self, request):
        data = request.data.copy()
        if not data.get("field_key"):
            data["field_key"] = _build_field_key(data.get("field_label"))
        data.setdefault("model_field", "")
        data.setdefault("form_step", 1)
        data.setdefault("section", "Additional Fields")
        data.setdefault(
            "sort_order",
            (LeadFormField.objects.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0) + 10,
        )
        data.setdefault("is_required", False)
        data.setdefault("is_locked", False)
        data.setdefault("is_active", True)
        serializer = LeadFormFieldSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        field = serializer.save()
        return Response(LeadFormFieldSerializer(field).data, status=status.HTTP_201_CREATED)


class LeadFormFieldDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, field_key):
        field = get_object_or_404(LeadFormField, field_key=field_key)
        blocked_keys = {"field_key", "model_field", "is_locked"}
        data = {
            key: value
            for key, value in request.data.items()
            if key not in blocked_keys
        }
        serializer = LeadFormFieldSerializer(field, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        field = serializer.save()
        return Response(LeadFormFieldSerializer(field).data)
