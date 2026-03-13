import asyncio
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.config import settings


async def verify_google_token(token: str) -> dict:
    """
    Verify Google ID token from mobile app.
    Returns dict with: sub, email, name, picture, email_verified
    """
    id_info = await asyncio.to_thread(
        id_token.verify_oauth2_token,
        token,
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )

    if id_info["iss"] not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Invalid token issuer")

    return id_info
