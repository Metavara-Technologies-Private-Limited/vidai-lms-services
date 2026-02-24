from rest_framework import serializers


class SendSMSSerializer(serializers.Serializer):
    to = serializers.CharField()
    message = serializers.CharField()


class MakeCallSerializer(serializers.Serializer):
    to = serializers.CharField()