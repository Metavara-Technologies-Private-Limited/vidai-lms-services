import requests
from django.conf import settings


def get_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": settings.LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def fetch_linkedin_account_details(token):
    url = "https://api.linkedin.com/rest/adAccounts"

    res = requests.get(
        url,
        headers=get_headers(token),
        params={"q": "search"},
    )

    if res.status_code != 200:
        print("❌ Failed to fetch ad accounts:", res.text)
        return None

    data = res.json().get("elements", [])
    if not data:
        print("❌ No ad accounts found")
        return None

    account = data[0]

    return {
        "account_id": str(account.get("id")),
        "org_urn": account.get("reference"),
    }


def create_campaign_group(token, account_id):
    url = "https://api.linkedin.com/rest/adCampaignGroups"

    payload = {
        "account": f"urn:li:sponsoredAccount:{account_id}",
        "name": "Default Campaign Group",
        "status": "ACTIVE",
    }

    res = requests.post(url, headers=get_headers(token), json=payload)

    if res.status_code not in [200, 201]:
        print("❌ Failed to create campaign group:", res.text)
        return None

    return res.json().get("id")