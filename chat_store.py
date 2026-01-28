# chat_store.py
from datetime import datetime
from typing import Dict, List

CHAT_STORE: Dict[str, dict] = {}


def create_chat(chat_id: str, repo_id: str):
    if chat_id not in CHAT_STORE:
        CHAT_STORE[chat_id] = {
            "repo_id": repo_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "messages": []
        }


# def append_message(
#     chat_id: str,
#     role: str,
#     content: str,
#     sources: List[str] | None = None,
#     tokens_used: int | None = None,
# ):
#     CHAT_STORE[chat_id]["messages"].append({
#         "role": role,
#         "content": content,
#         "sources": sources,
#         "tokens_used": tokens_used,
#         "created_at": datetime.utcnow().isoformat() + "Z"
#     })


from datetime import datetime
from typing import List

CHAT_STORE = {}

def append_message(
    chat_id: str,
    role: str,
    content: str,
    sources: List[str] | None = None,
    tokens_used: int | None = None,
):
    # ✅ Initialize chat if it doesn't exist
    if chat_id not in CHAT_STORE:
        CHAT_STORE[chat_id] = {
            "messages": []
        }

    CHAT_STORE[chat_id]["messages"].append({
        "role": role,
        "content": content,
        "sources": sources,
        "tokens_used": tokens_used,
        "created_at": datetime.utcnow().isoformat() + "Z"
    })


def get_chat(chat_id: str):
    return CHAT_STORE.get(chat_id)


def delete_chat(chat_id: str):
    return CHAT_STORE.pop(chat_id, None)
