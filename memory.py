# from langchain_core.chat_history import InMemoryChatMessageHistory

# # Store of session histories
# _STORE = {}

# def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
#     """
#     Return the chat history object for a session.
#     Create if not exists.
#     """
#     if session_id not in _STORE:
#         _STORE[session_id] = InMemoryChatMessageHistory()
#     return _STORE[session_id]


# memory.py

from langchain_core.chat_history import InMemoryChatMessageHistory

# In-memory store for all conversations
_STORE = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """
    session_id is treated as conversation_id.
    This function is intentionally unchanged in behavior.
    """
    if session_id not in _STORE:
        _STORE[session_id] = InMemoryChatMessageHistory()
    return _STORE[session_id]


def clear_all_conversations():
    """
    Clears all in-memory conversations.
    Used when a new repo is uploaded to avoid context bleed.
    """
    _STORE.clear()
