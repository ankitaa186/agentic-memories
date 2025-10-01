from __future__ import annotations

from typing import Any, Dict, Optional
from time import time
from os import getenv

import httpx
import logging
from jose import jwt


_jwks_cache: Dict[str, Any] = {}
_jwks_cache_ts: float = 0.0
_JWKS_TTL_SECONDS = 300.0
_logger = logging.getLogger("agentic_memories.cf")


def _get_jwks(team_domain: str) -> Dict[str, Any]:
    global _jwks_cache, _jwks_cache_ts
    now = time()
    if _jwks_cache and (now - _jwks_cache_ts) < _JWKS_TTL_SECONDS:
        return _jwks_cache
    url = f"https://{team_domain}.cloudflareaccess.com/cdn-cgi/access/certs"
    with httpx.Client(timeout=180.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_ts = now
        _logger.info("[cf.jwks] fetched team=%s ttl=%s", team_domain, _JWKS_TTL_SECONDS)
        return _jwks_cache


def verify_cf_access_token(token: str) -> Dict[str, Any]:
    """Verify Cloudflare Access JWT and return claims.

    Requires environment:
      - CF_ACCESS_AUD: Cloudflare Access application audience (UUID)
      - CF_ACCESS_TEAM_DOMAIN: Cloudflare team domain (e.g., 'memoryforge')
    """
    aud = getenv("CF_ACCESS_AUD")
    team = getenv("CF_ACCESS_TEAM_DOMAIN")
    if not aud or not team:
        raise ValueError("CF_ACCESS_AUD and CF_ACCESS_TEAM_DOMAIN must be set")

    jwks = _get_jwks(team)
    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=aud,
            options={"verify_at_hash": False},
        )
        _logger.info("[cf.verify] ok sub=%s aud=%s iss=%s", claims.get("sub"), claims.get("aud"), claims.get("iss"))
        return claims
    except Exception as exc:
        _logger.info("[cf.verify.error] %s", exc)
        raise ValueError(f"Invalid Cloudflare Access token: {exc}")


def extract_token_from_headers(headers: Dict[str, str]) -> Optional[str]:
    # Priority: explicit Cloudflare header
    cf_hdr = headers.get("cf-access-jwt-assertion") or headers.get("Cf-Access-Jwt-Assertion")
    if cf_hdr:
        return cf_hdr
    # Fallback: Authorization: Bearer <token>
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


