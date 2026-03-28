from django.shortcuts import get_object_or_404
from django.utils import timezone

from restapi.models import Campaign, CampaignSocialPost
import requests
import traceback
import logging

from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

def create_pending_social_post(campaign, platform):
    """
    Called when LMS sends campaign to Zapier.
    Creates a pending record.
    """
    return CampaignSocialPost.objects.create(
        campaign=campaign,
        platform_name=platform,
        status=CampaignSocialPost.PENDING
    )


def handle_zapier_callback(validated_data):
    """
    Updates CampaignSocialPost based on Zapier response.
    """

    campaign = get_object_or_404(
        Campaign,
        id=validated_data["campaign_id"]
    )

    social_post = CampaignSocialPost.objects.filter(
        campaign=campaign,
        platform_name=validated_data["platform"]
    ).order_by("-created_at").first()

    if not social_post:
        # fallback: create one if not found
        social_post = CampaignSocialPost.objects.create(
            campaign=campaign,
            platform_name=validated_data["platform"]
        )

    if validated_data["status"] == CampaignSocialPost.POSTED:
        social_post.mark_posted(
            post_id=validated_data.get("post_id")
        )
    else:
        social_post.mark_failed(
            error_message=validated_data.get("error_message")
        )

    return social_post




def get_facebook_post_insights(post_id, page_token):
    print("=" * 60)
    print("FB INSIGHTS: post_id =", post_id)

    result = {
        "post_id": post_id,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "impressions": 0,
        "reach": 0,
        "clicks": 0,
        "pending_review": True,
    }

    try:
        basic_url = f"https://graph.facebook.com/v19.0/{post_id}"
        basic_params = {
            "fields": "likes.summary(true),comments.summary(true)",
            "access_token": page_token,
        }
        basic_resp = requests.get(basic_url, params=basic_params, timeout=10)
        print("BASIC STATUS:", basic_resp.status_code, basic_resp.text[:200])

        if basic_resp.status_code == 200:
            basic_data = basic_resp.json()
            result["likes"] = (
                basic_data.get("likes", {}).get("summary", {}).get("total_count", 0)
            )
            result["comments"] = (
                basic_data.get("comments", {}).get("summary", {}).get("total_count", 0)
            )
            result["pending_review"] = False
    except Exception as e:
        print(f"FB insights fetch failed: {e}")

    print("FB INSIGHTS RESULT:", result)
    print("=" * 60)
    return result


def list_available_metrics(post_id, page_token):
    print("🚀 list_available_metrics CALLED")

    candidates = [
        "post_impressions",
        "post_impressions_unique",
        "post_engaged_users",
        "post_clicks",
        "post_reactions_by_type",
        "post_video_views",
        "post_video_complete_views_organic",
        "post_activity",
        "post_activity_unique",
    ]

    results = {}
    for metric in candidates:
        print(f"🔍 Testing metric: {metric}")
        url = f"https://graph.facebook.com/v19.0/{post_id}/insights"
        try:
            r = requests.get(
                url, params={"metric": metric, "access_token": page_token}, timeout=10
            )
            print(f"   Status: {r.status_code}")
            if r.status_code == 200:
                results[metric] = "✅ OK"
            else:
                error_msg = r.json().get("error", {}).get("message", "unknown error")
                results[metric] = f"❌ {error_msg}"
        except Exception as e:
            print(f"   EXCEPTION: {e}")
            results[metric] = f"💥 Exception: {str(e)}"

    print("✅ list_available_metrics DONE:", results)
    return results


# =====================================================
# HELPERS
# =====================================================
_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.tiff', '.bmp')


def _is_direct_image_url(url: str) -> bool:
    """Return True when the URL is likely a direct image."""
    if not url:
        return False
    clean = url.split("?")[0].split("#")[0].lower()
    if clean.endswith(_IMAGE_EXTENSIONS):
        return True
    _IMAGE_CDN_HOSTS = (
        "images.unsplash.com", "images.pexels.com", "i.imgur.com",
        "res.cloudinary.com", "cdn.pixabay.com", "media.istockphoto.com",
        "images.squarespace-cdn.com", "cdn.shopify.com",
        "storage.googleapis.com", "s3.amazonaws.com",
    )
    try:
        import urllib.parse
        host = urllib.parse.urlparse(url).netloc.lower()
        return any(host == cdn or host.endswith("." + cdn) for cdn in _IMAGE_CDN_HOSTS)
    except Exception:
        return False


def _download_image(image_url: str):
    """
    Download image bytes from a public URL.
    Returns (image_bytes, filename, content_type) or (None, None, None).
    """
    import re
    import urllib.parse

    if not _is_direct_image_url(image_url):
        print(f"Skipping non-image URL: {image_url}")
        return None, None, None

    wiki_upload_pattern = re.compile(
        r"https://upload\.wikimedia\.org/wikipedia/(?:commons|en)/"
        r"(?:thumb/[^/]+/[^/]+/|[^/]+/[^/]+/)([^/?#]+?)(?:/\d+px-[^/?#]+)?(?:[?#].*)?$",
        re.IGNORECASE,
    )
    wiki_match = wiki_upload_pattern.match(image_url)
    if wiki_match:
        import hashlib
        raw_filename = urllib.parse.unquote(wiki_match.group(1))
        clean_filename = re.sub(r"^\d+px-", "", raw_filename).replace(" ", "_")
        if clean_filename:
            clean_filename = clean_filename[0].upper() + clean_filename[1:]
        md5 = hashlib.md5(clean_filename.encode("utf-8")).hexdigest()
        md5_url = (
            f"https://upload.wikimedia.org/wikipedia/commons/"
            f"{md5[0]}/{md5[:2]}/{urllib.parse.quote(clean_filename, safe='')}"
        )
        print(f"Wikipedia URL detected. Filename: {clean_filename}, MD5 URL: {md5_url}")
        try:
            head = requests.head(md5_url, timeout=8, allow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; LMS-Bot/1.0)"})
            if head.status_code == 200:
                image_url = md5_url
            else:
                api_url = (
                    "https://commons.wikimedia.org/w/api.php"
                    f"?action=query&titles=File:{urllib.parse.quote(clean_filename)}"
                    "&prop=imageinfo&iiprop=url&format=json&redirects=1"
                )
                api_resp = requests.get(api_url, timeout=10,
                                        headers={"User-Agent": "Mozilla/5.0 (compatible; LMS-Bot/1.0)"})
                pages = api_resp.json().get("query", {}).get("pages", {})
                resolved_url = None
                for page_id, page in pages.items():
                    if page_id != "-1":
                        imageinfo = page.get("imageinfo", [])
                        if imageinfo:
                            resolved_url = imageinfo[0].get("url")
                            break
                if resolved_url:
                    image_url = resolved_url
                else:
                    return None, None, None
        except Exception as wiki_err:
            print(f"Wikipedia check failed: {wiki_err}. Trying MD5 URL.")
            image_url = md5_url

    import urllib.parse as _up
    parsed = _up.urlparse(image_url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "sec-fetch-dest": "image",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "cross-site",
    }
    try:
        resp = requests.get(image_url, timeout=20, headers=headers, allow_redirects=True)
        print(f"Image download status: {resp.status_code} from {image_url}")
        if resp.status_code != 200:
            return None, None, None
        image_bytes = resp.content
        raw_filename = image_url.split("?")[0].split("/")[-1]
        image_filename = _up.unquote(raw_filename) or "image.jpg"
        image_filename = re.sub(r"\s+", "_", image_filename)
        ext = image_filename.split(".")[-1].lower()
        content_type_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "tiff": "image/tiff", "bmp": "image/bmp",
        }
        content_type = content_type_map.get(ext, "image/jpeg")
        print(f"Image: {image_filename} | {len(image_bytes)} bytes | {content_type}")
        return image_bytes, image_filename, content_type
    except Exception as e:
        print(f"Failed to download image: {e}")
        return None, None, None

# =====================================================
# FACEBOOK POST HELPER
# =====================================================
def post_to_facebook(page_id, page_token, message, image_url=None):
    """Post a message (with optional image) to a Facebook Page."""
    print("=" * 60)
    print("FACEBOOK POST DEBUG")
    print(f"Page ID    : {page_id}")
    print(f"Token (20) : {page_token[:20] if page_token else 'NONE'}")
    print(f"Message    : {message}")
    print(f"Image URL  : {image_url}")
    print("=" * 60)

    if image_url:
        image_bytes, image_filename, content_type = _download_image(image_url)
        if image_bytes:
            url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
            print(f"Posting WITH image to: {url}")
            response = requests.post(
                url,
                data={"caption": message, "access_token": page_token},
                files={"source": (image_filename, image_bytes, content_type)},
            )
        else:
            print("Image download failed. Falling back to text-only post.")
            image_url = None

    if not image_url:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        print(f"Posting TEXT-ONLY to: {url}")
        response = requests.post(url, data={"message": message, "access_token": page_token})

    print(f"HTTP Status : {response.status_code}")
    print(f"Response    : {response.text}")
    try:
        result = response.json()
    except Exception:
        return {}
    if "id" in result:
        print(f"Facebook Post ID: {result['id']}")
    else:
        print(f"Facebook Post Failed: {result.get('error', result)}")
    print("=" * 60)
    return result


def create_instagram_media(ig_user_id, access_token, image_url, caption):
    url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload)
    return response.json()


def publish_instagram_media(ig_user_id, access_token, creation_id):
    url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload)
    return response.json()


def post_to_instagram(ig_user_id, access_token, message, image_url):
    print("POSTING TO INSTAGRAM")
    media = create_instagram_media(ig_user_id, access_token, image_url, message)
    creation_id = media.get("id")
    if not creation_id:
        print("Failed to create media:", media)
        return media
    publish = publish_instagram_media(ig_user_id, access_token, creation_id)
    print("Instagram publish response:", publish)
    return publish


def post_to_linkedin(access_token, author_urn, message, image_url=None):
    print("=" * 60)
    print("LINKEDIN POST DEBUG")
    print("Author URN:", author_urn)
    print("Message:", message)
    print("Image URL:", image_url)
    print("=" * 60)

    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": message},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    response = requests.post(url, headers=headers, json=payload)
    print("LinkedIn Status:", response.status_code)
    print("LinkedIn Response:", response.text)
    try:
        return response.json()
    except Exception:
        return {}


# =====================================================
# MAIL NOTIFICATION HELPERS
# =====================================================
def _send_lead_created_mail(lead):
    """Send internal notification email when a new lead is created."""
    try:
        send_mail(
            subject=f"Lead Created - {lead.full_name}",
            message=(
                f"New lead has been created in the system.\n\n"
                f"Name    : {lead.full_name}\n"
                f"Contact : {lead.contact_no}\n"
                f"Email   : {lead.email}\n"
                f"Status  : {lead.lead_status}\n"
                f"Lead ID : {lead.id}\n"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=True,
        )
        print(f"Lead Created mail sent for: {lead.full_name}")
    except Exception as e:
        print(f"Lead Created mail failed: {e}")


def _send_appointment_booked_mail(lead):
    """Send internal notification email when a lead status becomes Appointment."""
    try:
        send_mail(
            subject=f"Appointment Booked at Clinic - {lead.full_name}",
            message=(
                f"An appointment has been booked.\n\n"
                f"Patient Name : {lead.full_name}\n"
                f"Contact      : {lead.contact_no}\n"
                f"Email        : {lead.email}\n"
                f"Lead ID      : {lead.id}\n"
                f"Booked At    : {timezone.now().strftime('%d-%m-%Y %H:%M')}\n"
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=True,
        )
        print(f"Appointment Booked mail sent for: {lead.full_name}")
    except Exception as e:
        print(f"Appointment Booked mail failed: {e}")