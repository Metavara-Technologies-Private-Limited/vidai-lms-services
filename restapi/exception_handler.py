from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.utils.http import http_date
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    request = context.get("request", None)
    
    # Extract Request Details
    request_id = getattr(request, "request_id", "unknown")
    ip = request.META.get("REMOTE_ADDR", "unknown")
    path = request.path if request else "unknown"
    
    # Call DRF default handler
    response = exception_handler(exc, context)

    # Create custom log message
    log_message = (
        f"[ERROR][{datetime.utcnow()}]"
        f"[ReqID: {request_id}]"
        f"[IP: {ip}]\n"
        f"Path: {path}\n"
        f"Error: {str(exc)}"
    )

    logger.error(log_message)

    # If handled (400, 404)
    if response is not None:
        data = response.data if isinstance(response.data, dict) else {}

        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            error_message = detail
        else:
            error_message = None
            for key, value in data.items():
                if key in {"detail", "error", "request_id", "success", "status"}:
                    continue

                if isinstance(value, list) and value:
                    error_message = f"{key}: {value[0]}"
                    break
                if isinstance(value, str) and value.strip():
                    error_message = f"{key}: {value}"
                    break

            if not error_message:
                error_message = "Error occurred"

        response.data["error"] = error_message
        response.data["request_id"] = request_id
        response.data.pop("detail", None)

        return response

    # For unhandled 500 errors
    return Response(
        {"error": "Internal Server Error", "request_id": request_id},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
