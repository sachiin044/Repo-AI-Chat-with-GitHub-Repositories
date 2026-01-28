# auth/api_key_service.py

# Central place for all API key business logic
# Endpoints will call this, not each other
# Safe if any endpoint is deleted

# auth/api_key_service.py

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from auth.api_key import generate_api_key, hash_api_key
from supabase import create_client
import os

# Supabase client (same pattern as main.py)
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)


# -----------------------------
# CREATE API KEY (CORE LOGIC)
# -----------------------------
def create_api_key_internal(
    *,
    user_email: str,
    name: str,
    environment: Optional[str] = None,
    scopes: Optional[Dict[str, Any]] = None,
    expires_at: Optional[str] = None,
    ip_allowlist: Optional[Dict[str, Any]] = None,
):
    """
    Pure business logic:
    - Generates raw API key
    - Hashes key
    - Inserts into api_keys table
    - Returns raw key ONCE + metadata

    NO FastAPI
    NO request/response objects
    """

    raw_key = generate_api_key()
    hashed_key = hash_api_key(raw_key)

    payload = {
        "key_hash": hashed_key,
        "name": name,
        "user_email": user_email,
        "status": "active",
        "environment": environment,
        "scopes": scopes,
        "expires_at": expires_at,
        "ip_allowlist": ip_allowlist,
    }

    response = (
        supabase
        .table("api_keys")
        .insert(payload)
        .execute()
    )

    if not response.data:
        raise RuntimeError("Failed to create API key")

    row = response.data[0]

    return {
        "key_id": row["id"],
        "api_key": raw_key,   # shown ONCE
        "created_at": row["created_at"],
    }


# -----------------------------
# REVOKE API KEY (CORE LOGIC)
# -----------------------------
def revoke_api_key_internal(
    *,
    target_key_id: str,
    caller_email: str,
):
    """
    Revoke an API key owned by the same user_email.
    Idempotent & safe.
    """

    # Fetch target key
    target_resp = (
        supabase
        .table("api_keys")
        .select("id, user_email, status")
        .eq("id", target_key_id)
        .execute()
    )

    if not target_resp.data:
        raise RuntimeError("Target API key not found")

    target = target_resp.data[0]

    if target["user_email"] != caller_email:
        raise PermissionError("Not allowed to revoke this API key")

    if target["status"] == "revoked":
        return {"status": "already_revoked"}

    supabase.table("api_keys").update({
        "status": "revoked"
    }).eq("id", target_key_id).execute()

    return {"status": "revoked"}


# -----------------------------
# LIST API KEYS (LIGHTWEIGHT)
# -----------------------------
def list_api_keys_internal(
    *,
    user_email: str,
):
    """
    Lightweight listing.
    NO logs.
    NO aggregation.
    """

    resp = (
        supabase
        .table("api_keys")
        .select("id, name, environment, scopes, last_used_at")
        .eq("user_email", user_email)
        .execute()
    )

    return [
        {
            "key_id": r["id"],
            "name": r["name"],
            "environment": r.get("environment"),
            "scopes": r.get("scopes"),
            "last_used_at": r.get("last_used_at"),
        }
        for r in (resp.data or [])
    ]


# -----------------------------
# UPDATE API KEY METADATA
# -----------------------------
def update_api_key_internal(
    *,
    key_id: str,
    user_email: str,
    name: Optional[str] = None,
    scopes: Optional[Dict[str, Any]] = None,
    environment: Optional[str] = None,
):
    """
    Update metadata only.
    Does NOT touch secret, hash, status, expiry.
    """

    # Ownership check
    resp = (
        supabase
        .table("api_keys")
        .select("id, user_email")
        .eq("id", key_id)
        .execute()
    )

    if not resp.data:
        raise RuntimeError("API key not found")

    if resp.data[0]["user_email"] != user_email:
        raise PermissionError("Not allowed to update this API key")

    update_payload = {}

    if name is not None:
        update_payload["name"] = name
    if scopes is not None:
        update_payload["scopes"] = scopes
    if environment is not None:
        update_payload["environment"] = environment

    if update_payload:
        supabase.table("api_keys").update(
            update_payload
        ).eq("id", key_id).execute()

    return {"status": "updated"}
