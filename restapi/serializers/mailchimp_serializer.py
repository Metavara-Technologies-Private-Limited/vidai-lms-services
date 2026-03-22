from rest_framework import serializers


class MailchimpWebhookSerializer(serializers.Serializer):
    source = serializers.CharField()
    event_type = serializers.CharField()
    payload = serializers.JSONField()