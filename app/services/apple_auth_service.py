from datetime import datetime, timezone
import httpx
from jose import jwt
from app.config import settings

_apple_keys_cache = {"keys": None, "fetched_at": None}

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"


async def _get_apple_public_keys() -> list[dict]:
    """Fetch Apple's public keys with 24-hour caching."""
    now = datetime.now(timezone.utc)
    if (
        _apple_keys_cache["keys"]
        and _apple_keys_cache["fetched_at"]
        and (now - _apple_keys_cache["fetched_at"]).total_seconds() < 86400
    ):
        return _apple_keys_cache["keys"]

    async with httpx.AsyncClient() as client:
        response = await client.get(APPLE_KEYS_URL)
        response.raise_for_status()
        keys = response.json()["keys"]
        _apple_keys_cache["keys"] = keys
        _apple_keys_cache["fetched_at"] = now
        return keys


async def verify_apple_token(id_token_str: str) -> dict:
    """
    Verify Apple ID token from mobile app.
    Returns dict with: sub, email, email_verified
    """
    headers = jwt.get_unverified_header(id_token_str)
    apple_keys = await _get_apple_public_keys()

    matching_key = None
    for key in apple_keys:
        if key["kid"] == headers["kid"]:
            matching_key = key
            break

    if not matching_key:
        raise ValueError("No matching Apple public key found")

    payload = jwt.decode(
        id_token_str,
        matching_key,
        algorithms=["RS256"],
        audience=settings.APPLE_BUNDLE_ID,
        issuer=APPLE_ISSUER,
    )

    return payload
