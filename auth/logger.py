# auth/logger.py

import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)


def log_api_usage(api_key_id: str, endpoint: str):
    try:
        supabase.table("api_usage_logs").insert({
            "api_key_id": api_key_id,
            "endpoint": endpoint,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass  # logging must never block API
