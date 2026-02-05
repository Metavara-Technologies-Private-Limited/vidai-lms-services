import requests

def send_to_zapier(data):
    zapier_url = "https://hooks.zapier.com/hooks/catch/26329346/ul7z2zo/"

    try:
        response = requests.post(
            zapier_url,
            json=data,
            timeout=8
        )
        response.raise_for_status()
        return True

    except requests.exceptions.RequestException as e:
        print("Zapier error:", e)
        return False
