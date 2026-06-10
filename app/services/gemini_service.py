import base64
import re
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash-image"


class RateLimitedError(Exception):
    """Raised when the upstream Gemini API returns HTTP 429.

    `retry_after_seconds` is best-effort — parsed from the Retry-After header
    or Google's `google.rpc.RetryInfo` detail in the error body. May be None
    if the API didn't tell us when to try again.
    """

    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _parse_retry_after(response: httpx.Response) -> int | None:
    """Pull a retry-after hint from the Retry-After header or the
    google.rpc.RetryInfo entry in `error.details`. Returns whole seconds."""
    header_val = response.headers.get("Retry-After")
    if header_val:
        try:
            return int(float(header_val))
        except ValueError:
            pass  # HTTP-date format — ignore, fall through to body parse

    try:
        body = response.json()
        for detail in body.get("error", {}).get("details", []) or []:
            delay = detail.get("retryDelay")  # e.g. "30s", "1.5s"
            if isinstance(delay, str):
                m = re.match(r"^(\d+(?:\.\d+)?)s?$", delay)
                if m:
                    return max(1, int(float(m.group(1))))
    except Exception:  # noqa: BLE001 — best-effort parse, never let this raise
        pass

    return None


async def generate_image(
    prompt: str,
    reference_image_b64: str | None = None,
    aspect_ratio: str = "1:1",
) -> tuple[bytes, str | None]:
    """
    Generate or edit an image using Gemini Nano Banana model.

    Args:
        prompt: Text description of the image to generate/edit.
        reference_image_b64: Optional base64-encoded reference image for editing.
        aspect_ratio: Aspect ratio for the generated image.

    Returns:
        Tuple of (image_bytes, response_text).
    """
    parts = []

    if reference_image_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": reference_image_b64,
            }
        })

    parts.append({"text": prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
            },
        },
    }

    url = f"{GEMINI_API_URL}/{DEFAULT_MODEL}:generateContent"

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            url,
            json=payload,
            params={"key": settings.GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
        )

    if response.status_code == 429:
        retry_after = _parse_retry_after(response)
        logger.warning(
            "Gemini API rate-limited (429): retry_after=%ss body=%s",
            retry_after,
            response.text[:300],
        )
        raise RateLimitedError(
            "Image generation is rate-limited right now. Please try again in a moment.",
            retry_after_seconds=retry_after,
        )

    if response.status_code != 200:
        logger.error(f"Gemini API error {response.status_code}: {response.text}")
        raise ValueError(f"Image generation failed (status {response.status_code})")

    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No response from image generation model")

    response_parts = candidates[0].get("content", {}).get("parts", [])

    image_bytes = None
    response_text = None

    for part in response_parts:
        if "inline_data" in part and part["inline_data"].get("data"):
            image_bytes = base64.b64decode(part["inline_data"]["data"])
        elif "inlineData" in part and part["inlineData"].get("data"):
            image_bytes = base64.b64decode(part["inlineData"]["data"])
        elif "text" in part:
            response_text = part["text"]

    if not image_bytes:
        raise ValueError("No image data found in response")

    return image_bytes, response_text
