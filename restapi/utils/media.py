from django.conf import settings


def build_media_api_url(path: str) -> str:
    media_api_prefix = getattr(settings, "MEDIA_API_URL", "/api/media/")
    normalized_prefix = f"/{str(media_api_prefix).strip('/')}/"
    normalized_path = str(path or "").replace("\\", "/").lstrip("/")
    return f"{normalized_prefix}{normalized_path}"
