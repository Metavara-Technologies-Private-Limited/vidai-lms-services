from django.conf import settings
from restapi.models.reputation import ReviewRequest, ReviewRequestLead
from restapi.models.lead import Lead


def create_review_request(validated_data):

    lead_ids = validated_data.pop("lead_ids", [])

    # Create Review Request
    review_request = ReviewRequest.objects.create(**validated_data)

    # Fetch Leads
    leads = Lead.objects.filter(id__in=lead_ids)

    for lead in leads:

        rr_lead = ReviewRequestLead.objects.create(
            review_request=review_request,
            lead=lead
        )

        # ===============================
        # GENERATE LINK
        # ===============================
        review_link = ""

        if review_request.collect_on == "google":
            review_link = "https://g.page/review/your-clinic"

        elif review_request.collect_on == "form":
            review_link = f"{settings.FRONTEND_BASE_URL}/review/{review_request.id}/{lead.id}"

        elif review_request.collect_on == "both":
            review_link = f"{settings.FRONTEND_BASE_URL}/rating-gate/{review_request.id}"

        # ===============================
        # MESSAGE
        # ===============================
        message = f"""
Hi {lead.full_name},

Thank you for visiting our clinic.

Please share your experience here:
{review_link}

Regards,
Clinic Team
"""

        # ===============================
        # EMAIL
        # ===============================
        if review_request.mode == "email" and lead.email:

            from django.core.mail import send_mail

            send_mail(
                subject=review_request.subject or "Share Your Experience",
                message=message,
                from_email="noreply@clinic.com",
                recipient_list=[lead.email],
                fail_silently=True,
            )

            rr_lead.request_sent = True
            rr_lead.save()

        # ===============================
        # SMS
        # ===============================
        elif review_request.mode == "sms" and lead.contact_no:

            print(f"SMS sent to {lead.contact_no}: {message}")

            rr_lead.request_sent = True
            rr_lead.save()

        # ===============================
        # WHATSAPP
        # ===============================
        elif review_request.mode == "whatsapp" and lead.contact_no:

            print(f"WhatsApp sent to {lead.contact_no}: {message}")

            rr_lead.request_sent = True
            rr_lead.save()

    return review_request