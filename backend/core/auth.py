from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

from core.config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# In-process JWKS cache — refreshed once per hour
# ---------------------------------------------------------------------------

_jwks_keys: list[dict[str, Any]] = []
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600.0


async def _get_jwks_keys() -> list[dict[str, Any]]:
    global _jwks_keys, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_keys and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_keys

    url = settings.clerk_jwks_url
    if not url:
        logger.error("CLERK_PUBLISHABLE_KEY is not configured — JWT auth disabled")
        return []

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwks_keys = resp.json().get("keys", [])
        _jwks_fetched_at = now
        logger.info("JWKS refreshed", extra={"key_count": len(_jwks_keys)})
        return _jwks_keys


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Verify a Clerk-issued Bearer JWT and return the user ID (``sub`` claim).

    Raises HTTP 401 on any auth failure so the caller never receives an
    ambiguous error.  Internal errors are logged but not surfaced to the client.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        keys = await _get_jwks_keys()
        public_key = None
        for k in keys:
            if k.get("kid") == kid:
                public_key = jwk.construct(k)
                break

        if public_key is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        payload = jwt.decode(
            token,
            public_key.to_dict(),
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        user_id: str = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        return user_id

    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=401, detail="Authentication required")
    except Exception:
        logger.exception("Unexpected error during JWT verification")
        raise HTTPException(status_code=401, detail="Authentication required")
