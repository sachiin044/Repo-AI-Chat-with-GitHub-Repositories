# utils/repo_id.py
import hashlib


def get_repo_id(repo_url: str) -> str:
    return hashlib.sha256(repo_url.encode()).hexdigest()[:16]
