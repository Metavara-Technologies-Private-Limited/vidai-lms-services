# vidai-lms-services\restapi\services\campaign_social_post_service.py

from django.shortcuts import get_object_or_404


from restapi.models import Campaign, CampaignSocialPost
import requests
import traceback
import logging

from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from datetime import datetime

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from restapi.models import Campaign, CampaignSocialPost



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
    Handles Zapier callback after campaign/post creation.
    Persists LinkedIn provider ACK IDs needed for insights.
    """

    raw_id = (
        validated_data.get("internal_campaign_uuid")
        or validated_data.get("campaign_id")
    )

    platform = (
        validated_data.get("platform", "")
        .lower()
        .strip()
    )

    status_str = (
        validated_data.get("status", "")
        .upper()
        .strip()
    )

    try:

        # ------------------------------------
        # Resolve Campaign
        # ------------------------------------
        try:
            campaign = Campaign.objects.get(id=raw_id)

        except (Campaign.DoesNotExist, ValidationError):

            # fallback for legacy post callbacks
            campaign = get_object_or_404(
                Campaign,
                post_id=raw_id
            )


        # ------------------------------------
        # Social Post Tracking Record
        # ------------------------------------
        social_post = CampaignSocialPost.objects.filter(
            campaign=campaign,
            platform_name=platform
        ).order_by("-created_at").first()


        if not social_post:
            social_post = CampaignSocialPost.objects.create(
                campaign=campaign,
                platform_name=platform
            )


        # ------------------------------------
        # SUCCESS CALLBACK
        # ------------------------------------
        if status_str in ["POSTED", "SUCCESS"]:

            post_urn = (
                validated_data.get("post_urn")
                or validated_data.get("post_id")
            )

            campaign_urn = validated_data.get(
                "campaign_urn"
            )

            creative_urn = validated_data.get(
                "creative_urn"
            )

            account_id = validated_data.get(
                "account_id"
            )

            campaign_group_urn = validated_data.get(
                "campaign_group_urn"
            )

            ads_manager_url = validated_data.get(
                "ads_manager_url"
            )


            # ------------------------------------
            # LINKEDIN ACK PERSISTENCE
            # ------------------------------------
            if platform == "linkedin":

                if campaign_urn:
                    campaign.linkedin_campaign_urn = campaign_urn
                    campaign.linkedin_external_campaign_id = (
                        campaign_urn.split(":")[-1]
                    )

                if creative_urn:
                    campaign.linkedin_creative_urn = creative_urn
                    campaign.linkedin_creative_id = (
                        creative_urn.split(":")[-1]
                    )

                if account_id:
                    campaign.linkedin_account_id = account_id

                if post_urn:
                    campaign.linkedin_post_urn = post_urn

                if campaign_group_urn:
                    campaign.linkedin_campaign_group_urn = (
                        campaign_group_urn
                    )

                if ads_manager_url:
                    campaign.linkedin_ads_manager_url = (
                        ads_manager_url
                    )

                # store full provider callback
                campaign.linkedin_raw_response = validated_data

                campaign.status = Campaign.Status.SCHEDULED

                campaign.save(
                    update_fields=[
                        "linkedin_campaign_urn",
                        "linkedin_external_campaign_id",
                        "linkedin_creative_urn",
                        "linkedin_creative_id",
                        "linkedin_account_id",
                        "linkedin_post_urn",
                        "linkedin_campaign_group_urn",
                        "linkedin_ads_manager_url",
                        "linkedin_raw_response",
                        "status",
                    ]
                )

                print(
                    f"✅ LinkedIn campaign IDs saved for "
                    f"{campaign.campaign_name}"
                )


            # ------------------------------------
            # SOCIAL POST TRACKING
            # ------------------------------------
            social_post.creative_id = creative_urn
            social_post.ads_manager_url = ads_manager_url

            social_post.mark_posted(
                post_id=post_urn
            )


        # ------------------------------------
        # FAILED CALLBACK
        # ------------------------------------
        else:

            error_msg = (
                validated_data.get("msg")
                or validated_data.get("error_message")
                or "Unknown provider error"
            )

            social_post.mark_failed(
                error_message=str(error_msg)
            )

            campaign.status = Campaign.Status.FAILED
            campaign.save(update_fields=["status"])


        return social_post


    except Exception as e:
        logger.error(
            f"Zapier Callback Error: {str(e)}"
        )
        raise e




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
        "storage.googleapis.com", "s3.amazonaws.com","picsum.photos", 
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
    
    
def get_linkedin_ad_details(access_token, ad_creative_id):
    # Use the rest/adCreatives endpoint
    url = f"https://api.linkedin.com/rest/adCreatives/{ad_creative_id}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        # "LinkedIn-Version": "202509", # Must match your other calls
        "LinkedIn-Version": settings.LINKEDIN_API_VERSION
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    return None    
    
    
def get_linkedin_post_analytics(post_urn, access_token):
    """
    Fetches engagement (likes, comments, shares, clicks) for a specific Post URN.
    API: organizationalEntityShareStatistics
    """
    # Note: For LinkedIn, the 'author' is usually the organization URN 
    # extract the organization URN from the author field if possible
    # For now, we query specifically by the Share URN
    url = "https://api.linkedin.com/v2/organizationalEntityShareStatistics"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    params = {
        "q": "organizationalEntity",
        "organizationalEntity": settings.LINKEDIN_ORGANIZATION_URN, # e.g. 'urn:li:organization:12345'
        "shares": [post_urn]
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"LinkedIn Post Analytics Status: {response.status_code}")
        
        if response.status_code == 200:
            elements = response.json().get("elements", [])
            if elements:
                stats = elements[0].get("totalShareStatistics", {})
                return {
                    "impressions": stats.get("impressionCount", 0),
                    "clicks": stats.get("clickCount", 0),
                    "likes": stats.get("likeCount", 0),
                    "comments": stats.get("commentCount", 0),
                    "shares": stats.get("shareCount", 0),
                }
    except Exception as e:
        print(f"LinkedIn Post Analytics Error: {e}")
    return None


def get_linkedin_ads_analytics(access_token, account_id, pivot="CAMPAIGN", urn_list=None):
    """
    Fetches LinkedIn ad analytics using the REST API (202502+).
    Requires a 3-legged OAuth token with r_ads_reporting scope.
    """
    # Use the REST endpoint, NOT v2/adAnalyticsV2
    url = "https://api.linkedin.com/rest/adAnalytics"

    headers = {
        "Authorization": f"Bearer {access_token.strip()}",
        "X-Restli-Protocol-Version": "2.0.0",
        # "LinkedIn-Version": "202509",          # ← REQUIRED for REST endpoint
       "LinkedIn-Version": settings.LINKEDIN_API_VERSION
    }

    # Normalize account URN
    if account_id and not str(account_id).startswith("urn:li:sponsoredAccount:"):
        account_urn = f"urn:li:sponsoredAccount:{account_id}"  # ← sponsoredAccount, not adAccount
    else:
        account_urn = str(account_id).strip()

    params = {
        "q": "analytics",
        "pivot": pivot,
        "dateRange.start.day": 1,
        "dateRange.start.month": 1,
        "dateRange.start.year": 2024,
        "timeGranularity": "ALL",
        "fields": "impressions,clicks,costInLocalCurrency,externalWebsiteConversions,leads",
        "accounts[0]": account_urn,            # ← indexed array format for REST
    }

    # Add campaign filter with indexed array format
    if pivot == "CAMPAIGN" and urn_list:
        for i, urn in enumerate(urn_list):
            params[f"campaigns[{i}]"] = urn
    elif pivot == "CAMPAIGN_GROUP" and urn_list:
        for i, urn in enumerate(urn_list):
            params[f"campaignGroups[{i}]"] = urn

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"DEBUG: LinkedIn Query URL: {response.url}")
        print(f"DEBUG: LinkedIn Response Status: {response.status_code}")

        if response.status_code == 200:
            return response.json().get("elements", [])
        else:
            print(f"LinkedIn API Error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"LinkedIn Ads Analytics Exception: {e}")
        return None

def sync_linkedin_analytics_for_campaign(campaign):
    from restapi.models import CampaignSocialMediaConfig
    
    # 1. Get the config for THIS campaign using updated field logic
    config = CampaignSocialMediaConfig.objects.filter(
        campaign=campaign, 
        platform_name='linkedin'
    ).first()
    
    # ✅ FIX: Use 'access_token' instead of 'linkedin_access_token'
    if not config or not config.access_token:
        return {"error": "No LinkedIn configuration or token found"}
    
    access_token = config.access_token
    # ✅ FIX: Use 'platform_account_id' instead of 'li_ads_account_id'
    account_id = config.platform_account_id 
    
    results = {"post_metrics": None, "ad_metrics": None}

    # 2. Fetch Ad-level data (Sponsored)
    if campaign.li_campaign_urn:
        camp_urn = campaign.li_campaign_urn
        if not camp_urn.startswith("urn:li:"):
             camp_urn = f"urn:li:sponsoredCampaign:{camp_urn}"
            
        results["ad_metrics"] = get_linkedin_ads_analytics(
            access_token, 
            account_id, 
            pivot="CAMPAIGN", 
            urn_list=[camp_urn]
        )

        # 3. Update the campaign's budget_data JSON field
        if results["ad_metrics"] and len(results["ad_metrics"]) > 0:
            metrics = results["ad_metrics"][0] 
            
            impressions = metrics.get("impressions", 0)
            clicks = metrics.get("clicks", 0)
            spend = float(metrics.get("costInLocalCurrency", 0.0))
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (spend / clicks) if clicks > 0 else 0

            if campaign.budget_data is None:
                campaign.budget_data = {}

            campaign.budget_data.update({
                "impressions": impressions,
                "clicks": clicks,
                "spend": spend,
                "ctr": round(ctr, 2),
                "cpc": round(cpc, 2),
                "last_synced_at": datetime.now().isoformat()
            })
            
            campaign.save(update_fields=['budget_data'])
            print(f"Successfully synced metrics for {campaign.campaign_name}")
        else:
            print(f"No metrics found for URN: {campaign.li_campaign_urn}")

    return results

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