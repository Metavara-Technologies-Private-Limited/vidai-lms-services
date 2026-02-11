import requests
from django.conf import settings

def send_to_zapier(data):
    try:
        response = requests.post(
            settings.ZAPIER_WEBHOOK_URL,
            json=data,
            timeout=8
        )
        response.raise_for_status()
        return True

    except requests.exceptions.RequestException as e:
        print("Zapier error:", e)
        return False
