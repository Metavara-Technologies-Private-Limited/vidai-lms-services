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
        response.data["error"] = response.data.get("detail", "Error occurred")
        response.data["request_id"] = request_id
        response.data.pop("detail", None)

        return response

    # For unhandled 500 errors
    return Response(
        {"error": "Internal Server Error", "request_id": request_id},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
