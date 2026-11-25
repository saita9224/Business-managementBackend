# backend/throttling.py

"""
Lightweight fixed-window rate limiting for GraphQL mutations.

Uses Django's cache framework (locmem by default; swap CACHES to
Redis/Memcached for multi-process deployments). Fails open if the
cache backend is unavailable so auth is never blocked by infra issues.
"""

import logging

from django.core.cache import cache
from graphql import GraphQLError

logger = logging.getLogger(__name__)

RATE_LIMIT_MESSAGE = "Too many attempts. Please try again later."


def get_client_ip(info) -> str:
    """Best-effort client IP from the GraphQL context request."""
    request = getattr(info.context, "request", None)
    if request is None and isinstance(info.context, dict):
        request = info.context.get("request")
    if request is None:
        return "unknown"

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """
    Increment the counter for `key` and raise GraphQLError when the
    limit is exceeded within the window. `key` should be namespaced,
    e.g. "login:1.2.3.4:foo@bar.com".
    """
    cache_key = f"ratelimit:{key}"
    try:
        count = cache.get(cache_key, 0)
        if count >= limit:
            raise GraphQLError(RATE_LIMIT_MESSAGE)
        # set() refreshes the TTL, giving a sliding-ish window.
        cache.set(cache_key, count + 1, window_seconds)
    except GraphQLError:
        raise
    except Exception as exc:  # fail open on cache errors
        logger.warning("Rate limit check failed for %s: %s", key, exc)


def rate_limit_login(info, email: str) -> None:
    """5 attempts / 5 minutes per IP+email."""
    check_rate_limit(
        f"login:{get_client_ip(info)}:{email.strip().lower()}",
        limit=5,
        window_seconds=300,
    )


def rate_limit_auth_flow(info, bucket: str, email: str) -> None:
    """5 attempts / 15 minutes per IP+email for PIN/password flows."""
    check_rate_limit(
        f"{bucket}:{get_client_ip(info)}:{email.strip().lower()}",
        limit=5,
        window_seconds=900,
    )


def rate_limit_registration(info, email: str) -> None:
    """3 registration PIN requests / hour per IP+email."""
    check_rate_limit(
        f"regreq:{get_client_ip(info)}:{email.strip().lower()}",
        limit=3,
        window_seconds=3600,
    )


def rate_limit_ip(info, bucket: str, limit: int, window_seconds: int) -> None:
    """Generic per-IP limit (e.g. superadmin login, google auth)."""
    check_rate_limit(
        f"{bucket}:{get_client_ip(info)}",
        limit=limit,
        window_seconds=window_seconds,
    )
