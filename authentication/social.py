# authentication/social.py

"""
Stateless token verification for Google and Facebook.

Both functions receive the raw token string sent by the mobile app
and return a normalised dict on success, or raise ValueError on failure.

Returned dict shape:
    {
        "provider_id": str,   # Google 'sub' or Facebook 'id'
        "email":       str,
        "name":        str,
        "picture_url": str | None,
    }
"""

import httpx
from django.conf import settings

GOOGLE_TOKEN_INFO_URL   = "https://oauth2.googleapis.com/tokeninfo"
FACEBOOK_TOKEN_INFO_URL = "https://graph.facebook.com/me"


# ======================================================
# GOOGLE
# ======================================================

async def verify_google_token(id_token: str) -> dict:
    """
    Verify a Google id_token by sending it to Google's tokeninfo endpoint.
    Google validates the signature and expiry — we just check the result.
    """

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token},
        )

    if response.status_code != 200:
        raise ValueError("Google token verification failed")

    data = response.json()

    # Verify the token was issued for your app.
    # Set GOOGLE_CLIENT_ID in settings.py to your OAuth client ID.
    expected_client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    if expected_client_id and data.get("aud") != expected_client_id:
        raise ValueError("Google token was not issued for this app")

    if not data.get("sub"):
        raise ValueError("Google token missing subject identifier")

    return {
        "provider_id": data["sub"],
        "email":       data.get("email", ""),
        "name":        data.get("name", ""),
        "picture_url": data.get("picture"),
    }


# ======================================================
# FACEBOOK
# ======================================================

async def verify_facebook_token(access_token: str) -> dict:
    """
    Verify a Facebook user access token by calling the Graph API.
    Facebook validates the token server-side.
    """

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            FACEBOOK_TOKEN_INFO_URL,
            params={
                "fields":       "id,name,email,picture",
                "access_token": access_token,
            },
        )

    if response.status_code != 200:
        raise ValueError("Facebook token verification failed")

    data = response.json()

    if "error" in data:
        raise ValueError(f"Facebook error: {data['error'].get('message', 'unknown')}")

    if not data.get("id"):
        raise ValueError("Facebook token missing user id")

    picture_url = None
    if "picture" in data:
        picture_url = data["picture"].get("data", {}).get("url")

    return {
        "provider_id": data["id"],
        "email":       data.get("email", ""),
        "name":        data.get("name", ""),
        "picture_url": picture_url,
    }


# ======================================================
# DISPATCHER
# ======================================================

async def verify_social_token(provider: str, token: str) -> dict:
    """Single entry point — dispatches to the right verifier."""

    if provider == "google":
        return await verify_google_token(token)

    if provider == "facebook":
        return await verify_facebook_token(token)

    raise ValueError(f"Unsupported provider: {provider}")