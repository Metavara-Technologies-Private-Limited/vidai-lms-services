from django.db import transaction
from restapi.models import MarketingEvent


@transaction.atomic
def create_mailchimp_event(validated_data):

    event = MarketingEvent.objects.create(
        source=validated_data["source"],
        event_type=validated_data["event_type"],
        payload=validated_data["payload"],
    )

    return event