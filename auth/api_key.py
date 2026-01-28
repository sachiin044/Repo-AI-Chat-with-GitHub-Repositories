# auth/api_key.py

import secrets
import hashlib

API_KEY_PREFIX = "rl_live_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_hex(24)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
