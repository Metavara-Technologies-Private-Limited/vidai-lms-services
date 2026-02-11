import requests
from django.conf import settings


def send_to_zapier(data):
    try:
        print("🔔 Sending to Zapier...")
        print("🔹 Webhook URL:", settings.ZAPIER_WEBHOOK_URL)
        print("🔹 Payload:", data)

        response = requests.post(
            settings.ZAPIER_WEBHOOK_URL,
            json=data,
            timeout=8
        )

        print("✅ Zapier Status Code:", response.status_code)
        print("✅ Zapier Response:", response.text)

        return response.status_code

    except requests.exceptions.RequestException as e:
        print("❌ Zapier error:", str(e))
        return None
