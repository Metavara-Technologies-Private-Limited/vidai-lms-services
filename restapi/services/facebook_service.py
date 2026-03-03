import requests


def post_to_facebook(page_id, page_token, message):
    """
    Create Facebook post
    """

    url = f"https://graph.facebook.com/v18.0/{page_id}/feed"

    payload = {
        "message": message,
        "access_token": page_token,
    }

    response = requests.post(url, data=payload)

    print("FACEBOOK POST RAW:", response.json())

    return response.json()


def get_facebook_post_insights(post_id, page_token):
    """
    Fetch Facebook post insights (safe organic metrics)
    """

    url = f"https://graph.facebook.com/v18.0/{post_id}/insights"

    params = {
        # ✅ SAFE metrics for organic posts
        "metric": "post_impressions,post_impressions_unique,post_engaged_users",
        "access_token": page_token,
    }

    response = requests.get(url, params=params)

    print("FACEBOOK INSIGHTS RAW:", response.json())

    return response.json()