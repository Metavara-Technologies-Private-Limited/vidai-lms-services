"""
restapi/views/whatsapp_views.py

WhatsApp Business API views — template management + message sending.

Endpoints
─────────
  POST   /api/whatsapp/templates/create/   — submit new template to Meta
  GET    /api/whatsapp/templates/           — list all templates (synced from Meta)
  POST   /api/whatsapp/templates/sync/      — force-sync approval status from Meta
  DELETE /api/whatsapp/templates/<id>/      — delete a template from Meta + DB
  POST   /api/whatsapp/send/                — send single WhatsApp message
  POST   /api/whatsapp/bulk-send/           — send to multiple recipients
  GET    /api/whatsapp/messages/            — list sent messages (filterable)
"""

import logging

from rest_framework.views     import APIView
from rest_framework.response  import Response
from rest_framework           import status
from rest_framework.permissions import IsAuthenticated
from django.conf              import settings

from restapi.models           import WhatsAppTemplate, WhatsAppMessage
from restapi.serializers.whatsapp_serializers import (
    WhatsAppTemplateCreateSerializer,
    WhatsAppTemplateListSerializer,
    WhatsAppSendSerializer,
    WhatsAppBulkSendSerializer,
    WhatsAppMessageListSerializer,
)
from restapi.services.twilio_service import (
    create_whatsapp_template,
    list_whatsapp_templates,
    send_whatsapp_message,
    bulk_send_whatsapp,
)

logger = logging.getLogger(__name__)


def _clinic_id_from_request(request) -> int | None:
    """Extract clinic ID from request header or query param."""
    return (
        request.headers.get("X-Clinic-Id")
        or request.query_params.get("clinic_id")
        or None
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppTemplateCreateView(APIView):
    """
    POST /api/whatsapp/templates/create/

    Submit a new WhatsApp message template to Meta for approval.
    Stores the template in DB with status=PENDING immediately.
    Fires Zapier event: whatsapp_template_submitted
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WhatsAppTemplateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        d = serializer.validated_data

        try:
            result = create_whatsapp_template(
                name        = d["name"],
                category    = d["category"],
                language    = d["language"],
                body_text   = d["body_text"],
                variables   = d.get("variables", []),
                header_text = d.get("header_text", ""),
                footer_text = d.get("footer_text", ""),
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("WhatsAppTemplateCreateView unexpected error")
            return Response(
                {"success": False, "error": "Internal error. Check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success":     True,
                "message":     "Template submitted to Meta for approval.",
                "meta_result": result,
            },
            status=status.HTTP_201_CREATED,
        )


class WhatsAppTemplateListView(APIView):
    """
    GET /api/whatsapp/templates/

    Returns all templates from DB.
    Query params:
      ?status=APPROVED|PENDING|REJECTED   — filter by status
      ?sync=true                          — force sync from Meta before returning
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Optional force-sync
        if request.query_params.get("sync") == "true":
            try:
                list_whatsapp_templates()
            except Exception as exc:
                logger.warning("Template sync failed: %s", exc)

        qs = WhatsAppTemplate.objects.all()

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        serializer = WhatsAppTemplateListSerializer(qs, many=True)
        return Response({"success": True, "templates": serializer.data})


class WhatsAppTemplateSyncView(APIView):
    """
    POST /api/whatsapp/templates/sync/

    Force-sync all template statuses from Meta.
    Fires Zapier for any newly-approved templates.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            templates = list_whatsapp_templates()
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("WhatsAppTemplateSyncView unexpected error")
            return Response(
                {"success": False, "error": "Sync failed. Check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "success":        True,
            "message":        f"Synced {len(templates)} template(s) from Meta.",
            "total_synced":   len(templates),
        })


class WhatsAppTemplateDeleteView(APIView):
    """
    DELETE /api/whatsapp/templates/<id>/

    Deletes a template from Meta Graph API and removes it from DB.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        import requests as req

        template = WhatsAppTemplate.objects.filter(pk=pk).first()
        if not template:
            return Response(
                {"success": False, "error": "Template not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Delete from Meta
        if template.meta_template_id:
            from restapi.services.twilio_service import (
                META_GRAPH_BASE, _meta_headers, _require_setting
            )
            waba_id = _require_setting("META_WABA_ID")
            url     = f"{META_GRAPH_BASE}/{waba_id}/message_templates"
            params  = {
                "hsm_id": template.meta_template_id,
                "name":   template.name,
            }
            try:
                resp = req.delete(
                    url,
                    headers=_meta_headers(),
                    params=params,
                    timeout=10,
                )
                logger.info(
                    "WhatsAppTemplateDeleteView: Meta response %s", resp.status_code
                )
            except Exception as exc:
                logger.warning("Meta template delete failed: %s", exc)
                # Still delete from DB even if Meta call fails

        template.delete()

        return Response({
            "success": True,
            "message": "Template deleted from Meta and local DB.",
        })


# ─────────────────────────────────────────────────────────────────────────────
# SEND MESSAGE VIEWS
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppSendView(APIView):
    """
    POST /api/whatsapp/send/

    Send an approved WhatsApp template to a single number.
    Fires Zapier event: whatsapp_message_sent

    Body:
    {
        "lead_uuid":       "optional-uuid",
        "to_number":       "+919876543210",
        "template_name":   "appointment_reminder",
        "language":        "en",
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

        d          = serializer.validated_data
        clinic_id  = _clinic_id_from_request(request)

        try:
            wa_msg = send_whatsapp_message(
                lead_uuid       = str(d.get("lead_uuid") or ""),
                to_number       = d["to_number"],
                template_name   = d["template_name"],
                language        = d.get("language", "en"),
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

    Send an approved WhatsApp template to multiple recipients.
    Fires Zapier event: whatsapp_bulk_sent

    Body:
    {
        "template_name": "appointment_reminder",
        "language":      "en",
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

        try:
            results = bulk_send_whatsapp(
                recipients    = d["recipients"],
                template_name = d["template_name"],
                language      = d.get("language", "en"),
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
            "success":       True,
            "total":         len(results),
            "sent":          success_count,
            "failed":        failed_count,
            "results":       results,
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
      ?template_name=appointment_reminder
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WhatsAppMessage.objects.select_related("lead", "clinic", "template")

        clinic_id     = _clinic_id_from_request(request)
        lead_uuid     = request.query_params.get("lead_uuid")
        status_filter = request.query_params.get("status")
        template_name = request.query_params.get("template_name")

        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        if lead_uuid:
            qs = qs.filter(lead__id=lead_uuid)
        if status_filter:
            qs = qs.filter(status=status_filter.lower())
        if template_name:
            qs = qs.filter(template_name=template_name)

        serializer = WhatsAppMessageListSerializer(qs, many=True)
        return Response({
            "success":  True,
            "count":    qs.count(),
            "messages": serializer.data,
        })