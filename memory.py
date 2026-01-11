from langchain_core.chat_history import InMemoryChatMessageHistory

# Store of session histories
_STORE = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """
    Return the chat history object for a session.
    Create if not exists.
    """
    if session_id not in _STORE:
        _STORE[session_id] = InMemoryChatMessageHistory()
    return _STORE[session_id]
