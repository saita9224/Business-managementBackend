# authentication/social.py

"""
Google token verification.

Receives the id_token sent by the React Native app
(obtained via expo-auth-session / @react-native-google-signin)
and verifies it against Google's tokeninfo endpoint.

Returns a normalised dict on success, raises ValueError on failure.

Returned dict shape:
    {
        "provider_id": str,   # Google 'sub' — stable unique user ID
        "email":       str,
        "name":        str,
        "picture_url": str | None,
    }
"""

import httpx
from django.conf import settings

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


# ======================================================
# GOOGLE
# ======================================================

async def verify_google_token(id_token: str) -> dict:
    """
    Verify a Google id_token by sending it to Google's
    tokeninfo endpoint. Google validates the signature,
    expiry, and issuer — we just check the result and
    confirm the token was issued for our app.
    """

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token},
        )

    if response.status_code != 200:
        raise ValueError(
            "Google token verification failed — "
            "token may be expired or malformed"
        )

    data = response.json()

    # Confirm the token was issued for this specific app.
    # Prevents tokens from other Google OAuth apps being
    # used against your API.
    expected_client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    if expected_client_id and data.get("aud") != expected_client_id:
        raise ValueError(
            "Google token was not issued for this application"
        )

    if not data.get("sub"):
        raise ValueError("Google token missing subject identifier")

    if data.get("email_verified") != "true":
        raise ValueError("Google account email is not verified")

    return {
        "provider_id": data["sub"],
        "email":       data.get("email", ""),
        "name":        data.get("name", ""),
        "picture_url": data.get("picture"),
    }


# ======================================================
# ENTRY POINT
# ======================================================

async def verify_social_token(provider: str, token: str) -> dict:
    """
    Entry point called by the socialAuth mutation.
    Only Google is supported — passing any other provider
    raises a clear error rather than silently failing.
    """

    if provider == "google":
        return await verify_google_token(token)

    raise ValueError(
        f"Unsupported provider: '{provider}'. "
        f"Only 'google' is supported."
    )