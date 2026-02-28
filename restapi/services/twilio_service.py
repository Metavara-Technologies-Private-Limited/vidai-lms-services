from twilio.rest import Client
from django.conf import settings
from restapi.models import TwilioMessage, TwilioCall
from restapi.models.lead import Lead


# -------------------------------
# SEND SMS
# -------------------------------
def send_sms(lead_uuid, to_number, message_body):

    lead = Lead.objects.get(id=lead_uuid)

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    message = client.messages.create(
        body=message_body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number
    )

    TwilioMessage.objects.create(
        lead=lead,
        sid=message.sid,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=to_number,
        body=message_body,
        status=message.status,
        direction="outbound",
        raw_payload={"sid": message.sid, "status": message.status}
    )

    return message


# -------------------------------
# MAKE CALL
# -------------------------------
def make_call(lead_uuid, to_number):

    lead = Lead.objects.get(id=lead_uuid)

    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    call = client.calls.create(
        to=to_number,
        from_=settings.TWILIO_PHONE_NUMBER,
        url="http://demo.twilio.com/docs/voice.xml"
    )

    TwilioCall.objects.create(
        lead=lead,
        sid=call.sid,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=to_number,
        status=call.status,
        raw_payload={"sid": call.sid, "status": call.status}
    )

    return call