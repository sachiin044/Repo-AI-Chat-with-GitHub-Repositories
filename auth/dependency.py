# auth/dependency.py

import os
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
from dotenv import load_dotenv

from auth.api_key import hash_api_key
from auth.logger import log_api_usage
from auth.api_key_service import revoke_api_key_internal

from fastapi.security import HTTPBearer

security = HTTPBearer(auto_error=False)



load_dotenv()

# -----------------------------
# Supabase Client
# -----------------------------
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials

class RequireChatScopes:
    def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Security(security),
    ):
        return verify_api_key(
            request=request,
            credentials=credentials,
            required_scopes=["repo:read", "repo:explain"],
        )




# -----------------------------
# HTTP Bearer Security
# -----------------------------
security = HTTPBearer(auto_error=False)


# -----------------------------
# VERIFY API KEY (CORE DEPENDENCY)
# -----------------------------
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials

def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    required_scopes: Optional[List[str]] = None,
):
    """
    Verifies API key and returns api_key_id.

    Guarantees:
    - Same behavior as before for valid keys
    - Adds expiry + IP allowlist guards
    - Auto-revokes expired keys
    - Scope enforcement ONLY if required_scopes is provided
    - Does NOT break existing endpoints
    """

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    raw_key = credentials.credentials.strip()
    key_hash = hash_api_key(raw_key)

    # 🔥 DO NOT use .single()
    response = (
        supabase
        .table("api_keys")
        .select(
            "id, status, user_email, expires_at, ip_allowlist, scopes"
        )
        .eq("key_hash", key_hash)
        .execute()
    )

    rows = response.data or []

    if len(rows) == 0:
        raise HTTPException(status_code=401, detail="Invalid API key")

    key_row = rows[0]

    # -----------------------------
    # Status check (existing behavior)
    # -----------------------------
    if key_row["status"] != "active":
        raise HTTPException(status_code=403, detail="API key revoked")

    api_key_id = key_row["id"]

    # -----------------------------
    # Expiry guard (existing behavior)
    # -----------------------------
    expires_at = key_row.get("expires_at")
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(
                expires_at.replace("Z", "+00:00")
            )
        except Exception:
            expires_dt = None

        if expires_dt and expires_dt < datetime.now(timezone.utc):
            # Auto-revoke expired key
            revoke_api_key_internal(
                target_key_id=api_key_id,
                caller_email=key_row["user_email"],
            )
            raise HTTPException(
                status_code=401,
                detail="API key has expired",
            )

    # -----------------------------
    # IP allowlist guard (existing behavior)
    # -----------------------------
    ip_allowlist = key_row.get("ip_allowlist")

    if ip_allowlist:
        client_ip = request.client.host if request.client else None

        # Support both list and {"ips": [...]} formats
        if isinstance(ip_allowlist, dict):
            allowed_ips = ip_allowlist.get("ips", [])
        else:
            allowed_ips = ip_allowlist

        if client_ip not in allowed_ips:
            raise HTTPException(
                status_code=403,
                detail=f"IP {client_ip} is not allowed to use this API key",
            )

    # -----------------------------
    # Scope enforcement (NEW, OPTIONAL)
    # -----------------------------
    if required_scopes:
        key_scopes = key_row.get("scopes") or []

        missing_scopes = [
            scope for scope in required_scopes
            if scope not in key_scopes
        ]

        if missing_scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scopes: {missing_scopes}",
            )

    # -----------------------------
    # Expose api_key_id (existing behavior)
    # -----------------------------
    request.state.api_key_id = api_key_id

    # -----------------------------
    # Log usage (existing behavior)
    # -----------------------------
    log_api_usage(
        api_key_id=api_key_id,
        endpoint=request.url.path
    )

    return api_key_id



# -----------------------------
# SCOPE DECORATOR (OPTIONAL, SAFE)
# -----------------------------
def require_scopes(required_scopes: list[str]):
    """
    Decorator for enforcing API key scopes at endpoint level.
    Does NOT affect any endpoint unless explicitly used.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            api_key_id = kwargs.get("api_key_id")

            if not api_key_id:
                raise HTTPException(
                    status_code=401,
                    detail="Missing API key context",
                )

            resp = (
                supabase
                .table("api_keys")
                .select("scopes")
                .eq("id", api_key_id)
                .execute()
            )

            if not resp.data:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key",
                )

            scopes = resp.data[0].get("scopes") or {}

            for scope in required_scopes:
                if not scopes.get(scope):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Missing required scope: {scope}",
                    )

            return func(*args, **kwargs)

        return wrapper

    return decorator
