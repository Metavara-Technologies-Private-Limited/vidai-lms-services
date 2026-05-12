"""
restapi/views/whatsapp_views.py

WhatsApp Business API views — message sending + message history.

FIX: Uses your existing TemplateWhatsApp model (restapi_template_whatsapp)
     instead of a separate WhatsAppTemplate model.
     WhatsAppTemplateCreateView / ListView / SyncView / DeleteView are REMOVED
     because templates already exist in your DB via the UI.

Endpoints
─────────
  POST   /api/whatsapp/send/        — send single WhatsApp message
  POST   /api/whatsapp/bulk-send/   — send to multiple recipients
  GET    /api/whatsapp/messages/    — list sent messages (filterable)
"""

import logging

from rest_framework.views       import APIView
from rest_framework.response    import Response
from rest_framework             import status
from rest_framework.permissions import IsAuthenticated

from restapi.models.template_whatsapp import TemplateWhatsApp
from restapi.models              import WhatsAppMessage    # ← only new model
from restapi.serializers.whatsapp_serializers import (
    WhatsAppSendSerializer,
    WhatsAppBulkSendSerializer,
    WhatsAppMessageListSerializer,
)
from restapi.services.twilio_service import (
    send_whatsapp_message,
    bulk_send_whatsapp,
)

logger = logging.getLogger(__name__)


def _clinic_id_from_request(request):
    """Extract clinic ID from request header or query param."""
    return (
        request.headers.get("X-Clinic-Id")
        or request.query_params.get("clinic_id")
        or None
    )


# ─────────────────────────────────────────────────────────────────────────────
# SEND MESSAGE VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppSendView(APIView):
    """
    POST /api/whatsapp/send/

    Send a WhatsApp message using an existing TemplateWhatsApp from your DB.
    Fires Zapier event: whatsapp_message_sent

    Body:
    {
        "lead_uuid":       "optional-uuid",
        "to_number":       "+919876543210",
        "template_id":     "uuid-of-TemplateWhatsApp",
        "variable_values": ["John", "10 AM", "Dr. Smith"]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WhatsAppSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        d         = serializer.validated_data
        clinic_id = _clinic_id_from_request(request)

        # Fetch the template to get its body (used to build the message)
        template = TemplateWhatsApp.objects.get(id=d["template_id"])

        try:
            wa_msg = send_whatsapp_message(
                lead_uuid       = str(d.get("lead_uuid") or ""),
                to_number       = d["to_number"],
                template_id     = str(d["template_id"]),
                template_name   = template.name,
                template_body   = template.body,
                language        = "en",
                variable_values = d.get("variable_values", []),
                clinic_id       = int(clinic_id) if clinic_id else None,
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("WhatsAppSendView unexpected error")
            return Response(
                {"success": False, "error": "Failed to send message. Check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "success": True,
            "message": "WhatsApp message sent successfully.",
            "sid":     wa_msg.sid,
            "status":  wa_msg.status,
        }, status=status.HTTP_200_OK)


class WhatsAppBulkSendView(APIView):
    """
    POST /api/whatsapp/bulk-send/

    Send a WhatsApp message to multiple recipients using an existing
    TemplateWhatsApp from your DB.
    Fires Zapier event: whatsapp_bulk_sent

    Body:
    {
        "template_id": "uuid-of-TemplateWhatsApp",
        "recipients": [
            {
                "lead_uuid":       "optional-uuid",
                "to_number":       "+919876543210",
                "variable_values": ["John", "10 AM"]
            },
            ...
        ]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WhatsAppBulkSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        d         = serializer.validated_data
        clinic_id = _clinic_id_from_request(request)

        # Fetch the template once for all recipients
        template = TemplateWhatsApp.objects.get(id=d["template_id"])

        try:
            results = bulk_send_whatsapp(
                recipients    = d["recipients"],
                template_id   = str(d["template_id"]),
                template_name = template.name,
                template_body = template.body,
                language      = "en",
                clinic_id     = int(clinic_id) if clinic_id else None,
            )
        except Exception:
            logger.exception("WhatsAppBulkSendView unexpected error")
            return Response(
                {"success": False, "error": "Bulk send failed. Check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        success_count = sum(1 for r in results if r.get("status") != "error")
        failed_count  = len(results) - success_count

        return Response({
            "success": True,
            "total":   len(results),
            "sent":    success_count,
            "failed":  failed_count,
            "results": results,
        }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE HISTORY VIEW
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppMessageListView(APIView):
    """
    GET /api/whatsapp/messages/

    List all sent WhatsApp messages.
    Query params:
      ?clinic_id=1
      ?lead_uuid=<uuid>
      ?status=sent|delivered|failed
      ?template_id=<uuid>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WhatsAppMessage.objects.select_related("lead", "clinic", "template")

        clinic_id     = _clinic_id_from_request(request)
        lead_uuid     = request.query_params.get("lead_uuid")
        status_filter = request.query_params.get("status")
        template_id   = request.query_params.get("template_id")

        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        if lead_uuid:
            qs = qs.filter(lead__id=lead_uuid)
        if status_filter:
            qs = qs.filter(status=status_filter.lower())
        if template_id:
            qs = qs.filter(template_id=template_id)

        serializer = WhatsAppMessageListSerializer(qs, many=True)
        return Response({
            "success":  True,
            "count":    qs.count(),
            "messages": serializer.data,
        })