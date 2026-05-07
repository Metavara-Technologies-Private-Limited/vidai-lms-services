# =====================================================
# Imports (ONLY REQUIRED)
# =====================================================
import logging
import traceback

from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from django.conf import settings

from restapi.models import TwilioMessage, TwilioCall
from restapi.serializers.twilio_serializers import (
    SendSMSSerializer,
    MakeCallSerializer,
    TwilioMessageListSerializer,
    TwilioCallListSerializer,
)
from restapi.services.twilio_service import (
    send_sms,
    make_call,
    notify_zapier_event,
    generate_browser_call_token,
    browser_call_twiml,
    log_browser_call,
)

logger = logging.getLogger(__name__)


# =====================================================
# SEND SMS API
# =====================================================
class SendSMSAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Send SMS using Twilio",
        request_body=SendSMSSerializer,
        responses={
            200: "SMS Sent Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            logger.info(
                "SendSMSAPIView request received: payload_keys=%s",
                list(request.data.keys()) if hasattr(request, "data") else [],
            )

            serializer = SendSMSSerializer(
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            logger.info(
                "SendSMSAPIView hit: lead_uuid=%s to=%s",
                validated_data.get("lead_uuid"),
                validated_data.get("to"),
            )

            message = send_sms(
                lead_uuid=validated_data["lead_uuid"],
                to_number=validated_data["to"],
                message_body=validated_data["message"]
            )

            logger.info(
                "SendSMSAPIView success: sid=%s status=%s",
                message.sid,
                message.status,
            )

            return Response(
                {
                    "message": "SMS sent successfully",
                    "sid": message.sid,
                    "status": message.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio SMS Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# MAKE CALL API
# =====================================================
class MakeCallAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Make outbound call using Twilio",
        request_body=MakeCallSerializer,
        responses={
            200: "Call Initiated Successfully",
            400: "Validation Error",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    @transaction.atomic
    def post(self, request):
        try:
            logger.info(
                "MakeCallAPIView request received: payload_keys=%s",
                list(request.data.keys()) if hasattr(request, "data") else [],
            )

            serializer = MakeCallSerializer(
                data=request.data,
                context={"request": request}
            )

            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            logger.info(
                "MakeCallAPIView hit: lead_uuid=%s to=%s",
                validated_data.get("lead_uuid"),
                validated_data.get("to"),
            )

            call = make_call(
                lead_uuid=validated_data["lead_uuid"],
                to_number=validated_data["to"]
            )

            logger.info(
                "MakeCallAPIView success: sid=%s status=%s",
                call.sid,
                call.status,
            )

            return Response(
                {
                    "message": "Call initiated successfully",
                    "sid": call.sid,
                    "status": call.status,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.error("Twilio Call Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# SMS CALLBACK
# =====================================================
class TwilioSMSStatusCallbackAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request):
        try:
            payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)

            sid = payload.get("MessageSid") or payload.get("SmsSid")
            message_status = payload.get("MessageStatus") or payload.get("SmsStatus")
            to_number = payload.get("To")
            from_number = payload.get("From")
            error_code = payload.get("ErrorCode")
            error_message = payload.get("ErrorMessage")

            logger.info(
                "TwilioSMSStatusCallback received: sid=%s status=%s to=%s from=%s",
                sid,
                message_status,
                to_number,
                from_number,
            )

            twilio_message = (
                TwilioMessage.objects.select_related("lead")
                .filter(sid=sid)
                .first()
                if sid
                else None
            )

            lead_uuid = None
            if twilio_message:
                lead_uuid = str(twilio_message.lead_id) if twilio_message.lead_id else None
                merged_payload = twilio_message.raw_payload if isinstance(twilio_message.raw_payload, dict) else {}
                merged_payload["sms_status_callback"] = payload
                merged_payload["last_status_callback_at"] = timezone.now().isoformat()

                if message_status:
                    twilio_message.status = message_status
                twilio_message.raw_payload = merged_payload
                twilio_message.save(update_fields=["status", "raw_payload"])
            else:
                logger.warning("TwilioSMSStatusCallback SID not found in DB: sid=%s", sid)

            notify_zapier_event("sms_status_updated", {
                "lead_uuid": lead_uuid,
                "sid": sid,
                "status": message_status,
                "to_number": to_number,
                "from_number": from_number,
                "error_code": error_code,
                "error_message": error_message,
            })

            return Response({"message": "SMS callback processed"}, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio SMS Callback Error:\n" + traceback.format_exc())
            return Response({"error": "Internal Server Error"}, status=500)


# =====================================================
# CALL CALLBACK
# =====================================================
class TwilioCallStatusCallbackAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request):
        try:
            payload = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)

            sid = payload.get("CallSid")
            call_status = payload.get("CallStatus")
            to_number = payload.get("To")
            from_number = payload.get("From")
            direction = payload.get("Direction")
            call_duration = payload.get("CallDuration", "0")

            logger.info(
                "TwilioCallStatusCallback received: sid=%s status=%s to=%s from=%s",
                sid,
                call_status,
                to_number,
                from_number,
            )

            twilio_call = (
                TwilioCall.objects.select_related("lead")
                .filter(sid=sid)
                .first()
                if sid
                else None
            )

            lead_uuid = None
            if twilio_call:
                lead_uuid = str(twilio_call.lead_id) if twilio_call.lead_id else None

                merged_payload = (
                    twilio_call.raw_payload
                    if isinstance(twilio_call.raw_payload, dict)
                    else {}
                )

                merged_payload["call_status_callback"] = payload
                merged_payload["last_status_callback_at"] = timezone.now().isoformat()
                merged_payload["call_duration"] = call_duration

                if call_status:
                    twilio_call.status = call_status

                twilio_call.raw_payload = merged_payload
                twilio_call.save(update_fields=["status", "raw_payload"])

            else:
                logger.warning("TwilioCallStatusCallback SID not found in DB: sid=%s", sid)

            notify_zapier_event("call_status_updated", {
                "lead_uuid": lead_uuid,
                "sid": sid,
                "status": call_status,
                "to_number": to_number,
                "from_number": from_number,
                "direction": direction,
            })

            return Response(
                {"message": "Call callback processed"},
                status=status.HTTP_200_OK
            )

        except Exception:
            logger.error("Twilio Call Callback Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =====================================================
# SMS LIST (WITH clinic_id)
# =====================================================
class TwilioMessageListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve SMS list",
        manual_parameters=[
            openapi.Parameter("lead_uuid", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("clinic_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
        responses={200: TwilioMessageListSerializer(many=True)},
        tags=["Twilio"],
    )
    def get(self, request):
        try:
            lead_uuid = request.query_params.get("lead_uuid")
            clinic_id = request.query_params.get("clinic_id")

            queryset = TwilioMessage.objects.all()

            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            if clinic_id:
                queryset = queryset.filter(clinic__id=clinic_id)

            serializer = TwilioMessageListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio SMS Fetch Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =====================================================
# CALL LIST (WITH clinic_id)
# =====================================================
class TwilioCallListAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Retrieve Call list",
        manual_parameters=[
            openapi.Parameter("lead_uuid", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("clinic_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
        responses={200: TwilioCallListSerializer(many=True)},
        tags=["Twilio"],
    )
    def get(self, request):
        try:
            lead_uuid = request.query_params.get("lead_uuid")
            clinic_id = request.query_params.get("clinic_id")

            queryset = TwilioCall.objects.all()

            if lead_uuid:
                queryset = queryset.filter(lead__id=lead_uuid)

            if clinic_id:
                queryset = queryset.filter(clinic__id=clinic_id)

            serializer = TwilioCallListSerializer(queryset, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception:
            logger.error("Twilio Call Fetch Error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =====================================================
# BROWSER CALL: TOKEN
# GET /api/twilio/browser-call/token/?identity=agent_42
# =====================================================
class BrowserCallTokenAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Generate Twilio AccessToken for browser-based Voice SDK calls",
        manual_parameters=[
            openapi.Parameter(
                "identity",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                required=True,
                description="Unique agent/user identity string e.g. agent_42",
            ),
        ],
        responses={
            200: "{ token, identity }",
            400: "Missing identity",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    def get(self, request):
        identity = request.query_params.get("identity", "").strip()
        if not identity:
            return Response(
                {"error": "identity query param is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = generate_browser_call_token(identity)
            return Response(result, status=status.HTTP_200_OK)
        except Exception:
            logger.error("BrowserCallToken error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================
# BROWSER CALL: TWIML WEBHOOK
# POST /api/twilio/browser-call/twiml/
# Twilio hits this when browser SDK does Device.connect()
# =====================================================
@method_decorator(csrf_exempt, name="dispatch")
class BrowserCallTwiMLAPIView(APIView):

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request):
        try:
            to_number = (
                request.data.get("To")
                or request.data.get("to")
                or ""
            ).strip()

            record = bool(getattr(settings, "TWILIO_DIRECT_CALL_RECORD", False))
            twiml_str = browser_call_twiml(to_number=to_number, record=record)

            logger.info(
                "BrowserCallTwiMLAPIView: to=%s record=%s",
                to_number,
                record,
            )

            return HttpResponse(twiml_str, content_type="application/xml")

        except Exception:
            logger.error("BrowserCallTwiML error:\n" + traceback.format_exc())
            from twilio.twiml.voice_response import VoiceResponse
            r = VoiceResponse()
            r.say("An error occurred. Please try again.")
            return HttpResponse(str(r), content_type="application/xml", status=500)


# =====================================================
# BROWSER CALL: LOG
# POST /api/twilio/browser-call/log/
# Call from frontend once Twilio gives a real CallSid
# Body: { lead_uuid, to_number, sid, status, agent_identity }
# =====================================================
class BrowserCallLogAPIView(APIView):

    @swagger_auto_schema(
        operation_description="Log a browser-initiated Twilio call once a real CallSid is available",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["lead_uuid", "to_number", "sid", "status"],
            properties={
                "lead_uuid":      openapi.Schema(type=openapi.TYPE_STRING, description="Lead UUID"),
                "to_number":      openapi.Schema(type=openapi.TYPE_STRING, description="Patient phone E.164"),
                "sid":            openapi.Schema(type=openapi.TYPE_STRING, description="Twilio CallSid"),
                "status":         openapi.Schema(type=openapi.TYPE_STRING, description="Call status"),
                "agent_identity": openapi.Schema(type=openapi.TYPE_STRING, description="Agent identity string"),
            },
        ),
        responses={
            200: "Call logged successfully",
            400: "Bad request",
            500: "Internal Server Error",
        },
        tags=["Twilio"],
    )
    def post(self, request):
        lead_uuid      = request.data.get("lead_uuid")
        to_number      = request.data.get("to_number", "")
        sid            = request.data.get("sid", "")
        call_status    = request.data.get("status", "initiated")
        agent_identity = request.data.get("agent_identity", "")

        if not lead_uuid or not sid:
            return Response(
                {"error": "lead_uuid and sid are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            call_log = log_browser_call(
                lead_uuid=lead_uuid,
                to_number=to_number,
                sid=sid,
                status=call_status,
                agent_identity=agent_identity,
            )
            if not call_log:
                return Response(
                    {"error": "Lead not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"message": "Call logged successfully", "id": call_log.id},
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.error("BrowserCallLog error:\n" + traceback.format_exc())
            return Response(
                {"error": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )