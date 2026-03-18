import hashlib
import time
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/upload"
DESTROY_URL = f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/destroy"


def _generate_signature(params: dict) -> str:
    """Generate Cloudinary API signature."""
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if v is not None
    )
    to_sign = f"{sorted_params}{settings.CLOUDINARY_API_SECRET}"
    return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()


async def upload_image(image_bytes: bytes, folder: str = "image-ai-studio") -> dict:
    """
    Upload image bytes to Cloudinary.

    Returns:
        dict with 'url', 'secure_url', and 'public_id'.
    """
    import base64
    data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"

    timestamp = str(int(time.time()))
    params = {
        "folder": folder,
        "timestamp": timestamp,
    }
    signature = _generate_signature(params)

    form_data = {
        "file": data_uri,
        "folder": folder,
        "timestamp": timestamp,
        "api_key": settings.CLOUDINARY_API_KEY,
        "signature": signature,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(UPLOAD_URL, data=form_data)

    if response.status_code != 200:
        logger.error(f"Cloudinary upload failed {response.status_code}: {response.text}")
        raise ValueError(f"Image upload failed (status {response.status_code})")

    result = response.json()
    return {
        "url": result["url"],
        "secure_url": result["secure_url"],
        "public_id": result["public_id"],
    }


async def delete_image(public_id: str) -> bool:
    """Delete an image from Cloudinary by public_id."""
    timestamp = str(int(time.time()))
    params = {
        "public_id": public_id,
        "timestamp": timestamp,
    }
    signature = _generate_signature(params)

    form_data = {
        "public_id": public_id,
        "timestamp": timestamp,
        "api_key": settings.CLOUDINARY_API_KEY,
        "signature": signature,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(DESTROY_URL, data=form_data)

    if response.status_code != 200:
        logger.error(f"Cloudinary delete failed {response.status_code}: {response.text}")
        return False

    result = response.json()
    return result.get("result") == "ok"
