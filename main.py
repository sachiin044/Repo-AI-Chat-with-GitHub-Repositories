# main.py

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import uuid

from ingest import clone_repo, read_repo_files
from embed import create_vector_store
from rag import ask_question
from router import route_question
from followups import generate_followups
from auth.dependency import verify_api_key
from middleware.request_logger import RequestLoggingMiddleware
from memory import clear_all_conversations
from ingest import clone_private_repo

from auth.api_key import generate_api_key, hash_api_key
from supabase import create_client


from datetime import datetime, timezone
from chat_store import (
    create_chat,
    append_message,
    get_chat,
    delete_chat,
)
from utils.repo_id import get_repo_id

from auth.api_key_service import create_api_key_internal
from auth.api_key_service import list_api_keys_internal
from auth.api_key_service import update_api_key_internal
from auth.api_key_service import revoke_api_key_internal

from fastapi import BackgroundTasks




load_dotenv()


app = FastAPI(title="RepoLens Backend")
app.add_middleware(RequestLoggingMiddleware)

VECTOR_STORE = {}
REPO_MANIFEST = None
REPO_PATH = None


# ------------------ MODELS ------------------

class RepoRequest(BaseModel):
    repo_url: str


class ChatRequest(BaseModel):
    message: str
    repo_id: str
    chat_id: str | None = None
    context: dict | None = None
    files: list[str] | None = None

       
     


class GenerateKeyRequest(BaseModel):
    email: str
    name: str | None = "API Key"

class RevokeKeyRequest(BaseModel):
    api_key_id: str

class PrivateRepoRequest(BaseModel):
    repo_url: str
    github_token: str

class CreateApiKeyRequest(BaseModel):
    email: str
    name: str
    environment: str | None = None
    scopes: list[str] | None = None
    expires_at: str | None = None
    ip_allowlist: list[str] | None = None


class UpdateApiKeyRequest(BaseModel):
    name: str | None = None
    scopes: list[str] | None = None
    environment: str | None = None

class RegisterRepoRequest(BaseModel):
    provider: str
    repo_url: str
    branch: str | None = "main"
    visibility: str | None = "private"

class GithubPATRequest(BaseModel):
    token: str
    label: str
    scopes_expected: list[str]
    expires_at: str

class RegisterRepoRequest(BaseModel):
    provider: str
    repo_url: str
    branch: str | None = "main"
    visibility: str | None = "private"
    credential_id: str | None = None






# ------------------ HELPERS ------------------

def format_folder_structure(manifest: dict) -> str:
    lines = []
    for folder, files in manifest.get("structure", {}).items():
        if folder.startswith(".git"):
            continue
        folder_name = "repo" if folder == "." else folder
        lines.append(f"{folder_name}/")
        for f in files:
            lines.append(f"  ├─ {f}")
    return "\n".join(lines)


def read_file_content(repo_path: str, filename: str) -> str:
    for root, _, files in os.walk(repo_path):
        if filename in files:
            try:
                with open(os.path.join(root, filename), "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return "❌ Unable to read file."
    return "❌ File not found."


def is_greeting(question: str) -> bool:
    q = question.lower().strip()
    return q in {
        "hi", "hii", "hello", "hey", "hey there",
        "good morning", "good afternoon", "good evening"
    }

def is_last_question_query(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in [
        "last question",
        "previous question",
        "what did i ask",
        "what was my last"
    ])

def _index_repo_background(repo_id: str, repo_url: str):
    """
    Background task for indexing repository.
    Reuses existing sync logic without modification.
    """
    global VECTOR_STORE, REPO_MANIFEST, REPO_PATH

    # Clone repo
    REPO_PATH = clone_repo(repo_url)

    # Read files
    documents, REPO_MANIFEST = read_repo_files(REPO_PATH)

    # Build vector store
    # VECTOR_STORE = create_vector_store(documents)
    VECTOR_STORE[repo_id] = create_vector_store(documents)

    # Update indexed_at
    supabase.table("repos").update({
        "indexed_at": datetime.utcnow().isoformat() + "Z"
    }).eq("repo_id", repo_id).execute()




# ------------------ ROUTES ------------------

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "running"
    }


@app.post("/upload-repo")
def upload_repo(
    data: RepoRequest,
    api_key_id: str = Depends(verify_api_key),
):
    global VECTOR_STORE, REPO_MANIFEST, REPO_PATH

    # Reset all conversations when a new repo is uploaded
    clear_all_conversations()

    REPO_PATH = clone_repo(data.repo_url)
    documents, REPO_MANIFEST = read_repo_files(REPO_PATH)
    # VECTOR_STORE = create_vector_store(documents)
    repo_id = get_repo_id(data.repo_url)
    VECTOR_STORE[repo_id] = create_vector_store(documents)

    return {"status": "Repository indexed successfully"}

from auth.dependency import require_scopes
from auth.dependency import RequireChatScopes

from auth.dependency import require_scopes
from auth.dependency import RequireChatScopes

@app.post("/chat")
def chat(
    data: ChatRequest,
    api_key_id: str = Depends(RequireChatScopes()),
):

    global VECTOR_STORE, REPO_MANIFEST, REPO_PATH

    # -----------------------------
    # Chat ID (new + backward compatible)
    # -----------------------------
    # chat_id = data.chat_id or data.conversation_id or str(uuid.uuid4())
    chat_id = data.chat_id or str(uuid.uuid4())
    conversation_id = chat_id

    # -----------------------------
    # Repo indexed guard (PDF aligned)
    # -----------------------------
    repo_resp = (
        supabase
        .table("repos")
        .select("indexed_at")
        .eq("repo_id", data.repo_id)
        .execute()
    )

    if not repo_resp.data:
        return {
            "error": "Repository not registered"
        }

    if not repo_resp.data[0].get("indexed_at"):
        return {
            "error": "Repository is not indexed yet. Please index it first."
        }


    # # -----------------------------
    # # AUTO-INDEX LOGIC (MINIMALLY FIXED)
    # # -----------------------------
    # repo_id = data.repo_id

    # if not repo_id and data.repo_url:
    #     repo_id = get_repo_id(data.repo_url)

    # # 🔹 INDEX ONLY ONCE PER repo_id
    # if repo_id not in VECTOR_STORE:

    #     if data.repo_url:
    #         repo_url = data.repo_url

    #         if data.github_token:
    #             repo_url = repo_url.replace(
    #                 "https://",
    #                 f"https://{data.github_token}@"
    #             )

    #         REPO_PATH = clone_repo(repo_url)
    #         documents, REPO_MANIFEST = read_repo_files(REPO_PATH)
    #         VECTOR_STORE[repo_id] = create_vector_store(documents)

    #     # 🔹 create chat session (UNCHANGED)
    #     create_chat(chat_id, repo_id)

    # -----------------------------
    # Safety check (FIXED FOR DICT)
    # -----------------------------
    # if repo_id not in VECTOR_STORE:
    #     return {
    #         "chat_id": chat_id,
    #         "reply": "❌ No repository indexed yet.",
    #         "tokens_used": None,
    #         "sources": [],
    #         "created_at": datetime.utcnow().isoformat() + "Z",
    #     }

    # vector_store = VECTOR_STORE[repo_id]

    # -----------------------------
    # Vector store fetch (PDF aligned)
    # -----------------------------
    # vector_store = VECTOR_STORE.get(data.repo_id)

    # if vector_store is None:
    #     return {
    #         "error": "Repository vector store not loaded yet. Please try again later."
    #     }

    # -----------------------------
    # Vector store fetch (ROBUST)
    # -----------------------------
    vector_store = VECTOR_STORE.get(data.repo_id)

    if vector_store is None:
        # Repo is indexed in DB but vector store not in memory
        # Rehydrate vector store safely
        repo_resp = (
            supabase
            .table("repos")
            .select("repo_url")
            .eq("repo_id", data.repo_id)
            .execute()
        )

        if not repo_resp.data:
            return {
                "error": "Repository metadata missing."
            }

        repo_url = repo_resp.data[0]["repo_url"]

        # Rebuild vector store (same logic as indexing)
        repo_path = clone_repo(repo_url)
        documents, _ = read_repo_files(repo_path)
        vector_store = create_vector_store(documents)

        # Cache it
        VECTOR_STORE[data.repo_id] = vector_store


    # -----------------------------
    # 🔹 store user message (UNCHANGED)
    # -----------------------------
    append_message(
        chat_id=chat_id,
        role="user",
        content=data.message
    )

        # -----------------------------
    # Repo indexed guard (NEW)
    # -----------------------------
    # if data.repo_id:
    #     repo_resp = (
    #         supabase
    #         .table("repos")
    #         .select("indexed_at")
    #         .eq("repo_id", data.repo_id)
    #         .execute()
    #     )

    if not repo_resp.data:
        return {
            "error": "Repository not registered"
        }

        if not repo_resp.data[0].get("indexed_at"):
            return {
                "error": "Repository is not indexed yet. Please index it first."
            }


    # -----------------------------
    # Greeting handling (UNCHANGED)
    # -----------------------------
    if is_greeting(data.message):
        answer = (
            "Hi 👋 I’m here to help you understand this repository.\n\n"
            "You can ask things like:\n"
            "- What does a file do?\n"
            "- Show code of a file\n"
            "- Explain the architecture\n"
            "- How different parts work together"
        )

        append_message(
            chat_id=chat_id,
            role="assistant",
            content=answer
        )

        return {
            "chat_id": chat_id,
            "reply": answer,
            "tokens_used": None,
            "sources": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    route = route_question(data.message)

    # -----------------------------
    # 🔹 DETERMINISTIC MEMORY QUERY (UNCHANGED)
    # -----------------------------
    if is_last_question_query(data.message):
        chat = get_chat(chat_id)

        user_messages = [
            m for m in chat["messages"]
            if m["role"] == "user"
        ]

        if len(user_messages) < 2:
            answer = "This is your first question in this chat."
        else:
            answer = f'Your last question was: "{user_messages[-2]["content"]}"'

        append_message(
            chat_id=chat_id,
            role="assistant",
            content=answer
        )

        return {
            "chat_id": chat_id,
            "reply": answer,
            "tokens_used": 0,
            "sources": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    # -----------------------------
    # STRUCTURAL (UNCHANGED)
    # -----------------------------
    if route == "STRUCTURAL":
        answer = format_folder_structure(REPO_MANIFEST)

        append_message(
            chat_id=chat_id,
            role="assistant",
            content=answer
        )

        return {
            "chat_id": chat_id,
            "reply": answer,
            "tokens_used": None,
            "sources": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    # -----------------------------
    # CONTENT (UNCHANGED)
    # -----------------------------
    if route == "CONTENT":
        filename = next(
            (w for w in data.message.split() if w.endswith((".py", ".md", ".txt"))),
            None,
        )

        if not filename:
            answer = "❌ Please specify a file name."
            sources = []
        else:
            code = read_file_content(REPO_PATH, filename)
            answer = f"```python\n{code}\n```"
            sources = [filename]

        append_message(
            chat_id=chat_id,
            role="assistant",
            content=answer,
            sources=sources
        )

        return {
            "chat_id": chat_id,
            "reply": answer,
            "tokens_used": None,
            "sources": sources,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    # -----------------------------
    # SEMANTIC (RAG + MEMORY) (FIXED STORE)
    # -----------------------------
    response = ask_question(
        vector_store,
        question=data.message,
        session_id=conversation_id,
        context=data.context,
    )

    append_message(
        chat_id=chat_id,
        role="assistant",
        content=response["answer"],
        sources=response.get("sources"),
        tokens_used=response.get("tokens_used"),
    )

    return {
        "chat_id": chat_id,
        "reply": response["answer"],
        "tokens_used": response.get("tokens_used"),
        "sources": response.get("sources", []),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }




supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)

# @app.post("/generate-key")
# def generate_keys(data: GenerateKeyRequest):
#     """
#     Generate a new API key for a user (email).
#     Allows multiple keys per user.
#     Behavior unchanged.
#     """

#     try:
#         result = create_api_key_internal(
#             user_email=data.email,
#             name=data.name,
#         )
#     except Exception:
#         return {"error": "Failed to generate API key"}

#     return {
#         "api_key": result["api_key"],   # shown ONCE
#         "key_id": result["key_id"],
#         "status": "active",
#     }


@app.get("/chat/{chat_id}")
def get_chat_history(
    chat_id: str,
    api_key_id: str = Depends(verify_api_key),
):
    chat = get_chat(chat_id)

    if not chat:
        return {"error": "Chat not found"}

    return {
        "repo_id": chat["repo_id"],
        "messages": [
            {
                "role": m["role"],
                "content": m["content"]
            }
            for m in chat["messages"]
        ]
    }

@app.delete("/chat/{chat_id}")
def delete_chat_session(
    chat_id: str,
    api_key_id: str = Depends(verify_api_key),
):
    deleted = delete_chat(chat_id)

    if not deleted:
        return {"error": "Chat not found"}

    return {"status": "deleted"}


@app.get("/manage-keys")
def manage_keys(
    api_key_id: str = Depends(verify_api_key),
):
    """
    Return all API keys and usage logs
    scoped to the same user_email as the caller.
    JSON output only.
    """

    # 1️⃣ Get caller's user_email
    key_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        .eq("id", api_key_id)
        .execute()
    )

    if not key_resp.data:
        return {"error": "API key not found"}

    user_email = key_resp.data[0]["user_email"]

    # 2️⃣ Get all keys for this user
    keys_resp = (
        supabase
        .table("api_keys")
        .select("id, name, status, created_at, last_used_at")
        .eq("user_email", user_email)
        .execute()
    )

    keys = keys_resp.data or []

    result = []

    # 3️⃣ For each key, get logs
    for key in keys:
        logs_resp = (
            supabase
            .table("api_usage_logs")
            .select(
                "endpoint, method, status_code, duration_ms, created_at, request_id, error_message"
            )
            .eq("api_key_id", key["id"])
            .order("created_at", desc=True)
            .execute()
        )

        logs = logs_resp.data or []

        result.append({
            "api_key_id": key["id"],
            "name": key["name"],
            "status": key["status"],
            "created_at": key["created_at"],
            "last_used_at": key["last_used_at"],
            "usage": {
                "total_requests": len(logs),
                "error_count": sum(
                    1 for l in logs if l.get("status_code", 200) >= 400
                ),
            },
            "logs": logs,
        })

    return {
        "user_email": user_email,
        "keys": result,
    }

@app.post("/revoke-keys")
def revoke_keys(
    data: RevokeKeyRequest,
    caller_api_key_id: str = Depends(verify_api_key),
):
    """
    Revoke an API key owned by the same user_email.
    """

    # 1️⃣ Get caller's user_email
    caller_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        .eq("id", caller_api_key_id)
        .execute()
    )

    if not caller_resp.data:
        return {"error": "Caller API key not found"}

    caller_email = caller_resp.data[0]["user_email"]

    # 2️⃣ Get target key
    target_resp = (
        supabase
        .table("api_keys")
        .select("id, user_email, status")
        .eq("id", data.api_key_id)
        .execute()
    )

    if not target_resp.data:
        return {"error": "Target API key not found"}

    target_key = target_resp.data[0]

    # 3️⃣ Ownership check
    if target_key["user_email"] != caller_email:
        return {"error": "You are not allowed to revoke this API key"}

    # 4️⃣ Already revoked check
    if target_key["status"] == "revoked":
        return {
            "status": "ok",
            "message": "API key already revoked",
            "api_key_id": data.api_key_id,
        }

    # 5️⃣ Revoke key
    supabase.table("api_keys").update({
        "status": "revoked"
    }).eq("id", data.api_key_id).execute()

    return {
        "status": "success",
        "message": "API key revoked successfully",
        "api_key_id": data.api_key_id,
    }

# @app.post("/private-repo-access")
# def private_repo_access(
#     data: PrivateRepoRequest,
#     api_key_id: str = Depends(verify_api_key),
# ):
#     """
#     Access and index a private GitHub repository using a per-request token.
#     Replaces the currently indexed repository.
#     """

#     global VECTOR_STORE, REPO_MANIFEST, REPO_PATH

#     # Reset conversations (same behavior as /upload-repo)
#     clear_all_conversations()

#     try:
#         REPO_PATH = clone_private_repo(
#             data.repo_url,
#             data.github_token
#         )
#     except Exception:
#         return {"error": "Failed to access private repository. Check token and repo URL."}

#     documents, REPO_MANIFEST = read_repo_files(REPO_PATH)
#     VECTOR_STORE = create_vector_store(documents)

#     return {
#         "status": "Private repository indexed successfully"
#     }


from ingest import clone_private_repo

@app.post("/private-repo-access")
def private_repo_access(
    data: PrivateRepoRequest,
    api_key_id: str = Depends(verify_api_key),
):
    """
    Access and index a private GitHub repository using a per-request token.
    Replaces the currently indexed repository.
    """

    global VECTOR_STORE, REPO_MANIFEST, REPO_PATH

    if not data.repo_url or not data.github_token:
        return {"error": "repo_url and github_token are required"}

    clear_all_conversations()

    try:
        REPO_PATH = clone_private_repo(
            data.repo_url,
            data.github_token
        )
    except Exception as e:
        return {
            "error": "Failed to access private repository",
            "details": str(e)
        }

    documents, REPO_MANIFEST = read_repo_files(REPO_PATH)
    # VECTOR_STORE = create_vector_store(documents)
    repo_id = get_repo_id(data.repo_url)
    VECTOR_STORE[repo_id] = create_vector_store(documents)


    return {
        "status": "Private repository indexed successfully"
    }

@app.post("/api-keys")
def create_api_keys(
    data: CreateApiKeyRequest):

    # 2️⃣ Call shared internal logic
    try:
        result = create_api_key_internal(
            user_email=data.email,
            name=data.name,
            environment=data.environment,
            scopes=data.scopes,
            expires_at=data.expires_at,
            ip_allowlist=data.ip_allowlist,
        )
    except Exception:
        return {"error": "Failed to create API key"}

    return {
        "key_id": result["key_id"],
        "api_key": result["api_key"],  # shown ONCE
        "created_at": result["created_at"],
    }

@app.get("/api-keys")
def list_api_keys(
    api_key_id: str = Depends(verify_api_key),
):
    """
    Lightweight list of API keys.
    No logs. No usage aggregation.
    """

    # 1️⃣ Resolve caller email
    key_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        .eq("id", api_key_id)
        .execute()
    )

    if not key_resp.data:
        return {"error": "API key not found"}

    user_email = key_resp.data[0]["user_email"]

    # 2️⃣ Internal fetch (may return more fields)
    keys = list_api_keys_internal(user_email=user_email)

    # 3️⃣ 🔒 Normalize to PDF contract
    return [
        {
            "key_id": k["key_id"],
            "name": k["name"],
            "environment": k.get("environment"),
            "scopes": k.get("scopes", []),
            "last_used_at": k.get("last_used_at"),
        }
        for k in keys
    ]

from fastapi import Body

# @app.patch("/api-keys/{key_id}")
# def update_api_key(
#     key_id: str,
#     data: UpdateApiKeyRequest = Body(...),
#     api_key_id: str = Depends(verify_api_key),
# ):
#     """
#     Update API key metadata only.
#     """

#     # 1️⃣ Resolve caller email (reuse existing pattern)
#     key_resp = (
#         supabase
#         .table("api_keys")
#         .select("user_email")
#         .eq("id", api_key_id)
#         .execute()
#     )

#     if not key_resp.data:
#         return {"error": "API key not found"}

#     user_email = key_resp.data[0]["user_email"]

#     # 2️⃣ Call internal update logic
#     try:
#         update_api_key_internal(
#             key_id=key_id,
#             user_email=user_email,
#             name=data.name,
#             scopes=data.scopes,
#             # environment=data.environment,
#         )
#     except PermissionError:
#         return {"error": "You are not allowed to update this API key"}
#     except Exception:
#         return {"error": "Failed to update API key"}

#     return {"status": "updated"}


# @app.patch("/api-keys/{key_id}")
# def update_api_key(
#     key_id: str,
#     data: UpdateApiKeyRequest = Body(...),
#     api_key_id: str = Depends(verify_api_key),
# ):
#     """
#     Update API key metadata only.
#     """

#     key_resp = (
#         supabase
#         .table("api_keys")
#         .select("user_email")
#         .eq("id", api_key_id)
#         .execute()
#     )

#     if not key_resp.data:
#         return {"error": "API key not found"}

#     user_email = key_resp.data[0]["user_email"]

#     update_api_key_internal(
#         key_id=key_id,
#         user_email=user_email,
#         name=data.name,
#         scopes=data.scopes,
#         environment=data.environment,
#     )

#     return {"status": "updated"}

from fastapi import Body

@app.patch("/api-keys/{key_id}")
def update_api_key(
    key_id: str,
    data: UpdateApiKeyRequest = Body(..., embed=False),
    api_key_id: str = Depends(verify_api_key),
):
    """
    Update API key metadata only.
    """

    key_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        .eq("id", api_key_id)
        .execute()
    )

    if not key_resp.data:
        return {"error": "API key not found"}

    user_email = key_resp.data[0]["user_email"]

    update_api_key_internal(
        key_id=key_id,
        user_email=user_email,
        name=data.name,
        scopes=data.scopes,
    )

    return {"status": "updated"}


@app.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: str,
    api_key_id: str = Depends(verify_api_key),
):
    """
    Revoke an API key (alias of /revoke-keys).
    """

    # 1️⃣ Resolve caller email (reuse existing pattern)
    key_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        .eq("id", api_key_id)
        .execute()
    )

    if not key_resp.data:
        return {"error": "API key not found"}

    caller_email = key_resp.data[0]["user_email"]

    # 2️⃣ Call shared revoke logic
    try:
        result = revoke_api_key_internal(
            target_key_id=key_id,
            caller_email=caller_email,
        )
    except PermissionError:
        return {"error": "You are not allowed to revoke this API key"}
    except Exception:
        return {"error": "Failed to revoke API key"}

    # Normalize response
    if result.get("status") == "already_revoked":
        return {
            "status": "ok",
            "message": "API key already revoked",
            "api_key_id": key_id,
        }

    return {
        "status": "success",
        "message": "API key revoked successfully",
        "api_key_id": key_id,
    }

@app.post("/repos/register")
def register_repo(data: RegisterRepoRequest):
    """
    Register a repository and return repo_id.
    Does NOT index the repo.
    No authentication required.
    """

    # 🔐 PDF-required guard (ADD THIS)
    if data.visibility == "private" and not data.credential_id:
        return {"error": "credential_id required for private repositories"}

    # 1️⃣ Generate deterministic repo_id (already used in /chat)
    repo_id = get_repo_id(data.repo_url)

    # 2️⃣ Check if repo already registered
    existing = (
        supabase
        .table("repos")
        .select("repo_id")
        .eq("repo_id", repo_id)
        .execute()
    )

    if existing.data:
        return {
            "repo_id": repo_id,
            "status": "already_registered",
        }

    # 3️⃣ Insert repo metadata
    supabase.table("repos").insert({
        "repo_id": repo_id,
        "repo_url": data.repo_url,
        "credential_id": data.credential_id, 
    }).execute()

    return {
        "repo_id": repo_id,
        "status": "registered",
    }

@app.post("/repos/{repo_id}/index")
def index_repo(repo_id: str, background_tasks: BackgroundTasks):
    """
    Starts async repository indexing.
    No authentication required.
    """

    # 1️⃣ Fetch repo metadata
    repo_resp = (
        supabase
        .table("repos")
        .select("repo_url")
        .eq("repo_id", repo_id)
        .execute()
    )

    if not repo_resp.data:
        return {"error": "Repository not registered"}

    repo_url = repo_resp.data[0]["repo_url"]

    # 2️⃣ Start background indexing
    background_tasks.add_task(
        _index_repo_background,
        repo_id,
        repo_url,
    )

    # 3️⃣ Return immediately (PDF compliant)
    return {
        "index_id": f"idx_{repo_id}",
        "status": "started"
    }


@app.get("/repos/{repo_id}/status")
def repo_status(repo_id: str):
    """
    Get repository indexing status.
    No authentication required.
    """

    repo_resp = (
        supabase
        .table("repos")
        .select("indexed_at, created_at")
        .eq("repo_id", repo_id)
        .execute()
    )

    if not repo_resp.data:
        return {"error": "Repository not registered"}

    repo = repo_resp.data[0]

    if repo.get("indexed_at"):
        status = "completed"
    else:
        status = "registered"

    return {
        "repo_id": repo_id,
        "status": status,
        "last_indexed_at": repo.get("indexed_at"),
    }


@app.get("/repos/{repo_id}/tree")
def repo_tree(repo_id: str):
    if REPO_MANIFEST is None:
        return {"error": "Repository not indexed"}

    tree = []

    for folder, files in REPO_MANIFEST.get("structure", {}).items():

        # 🚫 Skip .git folder entirely
        if folder.startswith(".git"):
            continue

        folder_path = "" if folder == "." else f"{folder}/"

        if folder_path:
            tree.append({
                "path": folder_path,
                "type": "dir"
            })

        for f in files:
            # 🚫 Skip .git files just in case
            if f.startswith(".git"):
                continue

            tree.append({
                "path": f"{folder_path}{f}",
                "type": "file"
            })

    return {
        "repo_id": repo_id,
        "tree": tree
    }



@app.get("/repos/{repo_id}/files")
def repo_file(repo_id: str, path: str):
    """
    Get file content from repository.
    Requires repo to be indexed.
    No authentication required.
    """

    if REPO_PATH is None:
        return {"error": "Repository not indexed"}

    try:
        content = read_file_content(REPO_PATH, path)
    except Exception:
        return {"error": "File not found"}

    return {
        "repo_id": repo_id,
        "path": path,
        "content": content
    }



# from utils.crypto import encrypt_token
# from utils.github import validate_github_pat

# @app.post("/credentials/github/pat")
# def register_github_pat(
#     data: GithubPATRequest = Body(..., embed=False),
#     api_key_id: str = Depends(verify_api_key),
# ):
#     """
#     Registers a GitHub Personal Access Token.
#     """

#     # 1️⃣ Resolve user_email from API key
#     key_resp = (
#         supabase
#         .table("api_keys")
#         .select("user_email")
#         .eq("id", api_key_id)
#         .execute()
#     )

#     if not key_resp.data:
#         return {"error": "API key not found"}

#     user_email = key_resp.data[0]["user_email"]

#     # 2️⃣ Validate token with GitHub
#     try:
#         granted_scopes = validate_github_pat(
#             token=data.token,
#             scopes_expected=data.scopes_expected,
#         )
#     except Exception as e:
#         return {"error": str(e)}

#     # 3️⃣ Encrypt token (NO RAW STORAGE)
#     encrypted = encrypt_token(data.token)

#     credential_id = f"cred_{uuid.uuid4().hex}"

#     # 4️⃣ Store credential
#     supabase.table("credentials").insert({
#         "id": credential_id,
#         "user_email": user_email,
#         "provider": "github",
#         "label": data.label,
#         "encrypted_token": encrypted,
#         "scopes": granted_scopes,
#         "expires_at": data.expires_at,
#     }).execute()

#     return {
#         "credential_id": credential_id,
#         "status": "validated"
#     }


from utils.crypto import encrypt_token
from utils.github import validate_github_pat

@app.post("/credentials/github/pat")
def register_github_pat(
    data: GithubPATRequest,
    # api_key_id: str = Depends(verify_api_key),
):
    """
    Registers a GitHub Personal Access Token.
    """

    # 1️⃣ Resolve user_email from API key
    key_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        # .eq("id", api_key_id)
        .execute()
    )

    if not key_resp.data:
        return {"error": "API key not found"}

    user_email = key_resp.data[0]["user_email"]

    # 2️⃣ Validate token with GitHub
    try:
        granted_scopes = validate_github_pat(
            token=data.token,
            scopes_expected=data.scopes_expected,
        )
    except Exception as e:
        return {"error": str(e)}

    # ================================
    # ⬅️ ADD: OVER-SCOPE VALIDATION (NOTION)
    # ================================
    extra_scopes = set(granted_scopes) - set(data.scopes_expected)
    if extra_scopes:
        return {
            "error": f"Token has extra scopes: {list(extra_scopes)}"
        }

    # ================================
    # ⬅️ ADD: EXPIRY VALIDATION (NOTION)
    # ================================
    if not data.expires_at:
        return {"error": "Token expiry is required"}

    try:
        expires = datetime.fromisoformat(
            data.expires_at.replace("Z", "+00:00")
        )
    except Exception:
        return {"error": "Invalid expires_at format"}

    if expires <= datetime.now(timezone.utc):
        return {"error": "Token is already expired"}

    # 3️⃣ Encrypt token (NO RAW STORAGE)
    encrypted = encrypt_token(data.token)

    credential_id = str(uuid.uuid4())

    # 4️⃣ Store credential
    supabase.table("credentials").insert({
        "id": credential_id,
        "user_email": user_email,
        "provider": "github",
        "label": data.label,
        "encrypted_token": encrypted,
        "scopes": granted_scopes,
        "expires_at": data.expires_at,
    }).execute()

    return {
        "credential_id": credential_id,
        "status": "validated"
    }

@app.delete("/credentials/{credential_id}")
def revoke_credential(
    credential_id: str,
    # api_key_id: str = Depends(verify_api_key),
):
    """
    Revokes a stored credential.
    """

    # 1️⃣ Resolve caller email
    key_resp = (
        supabase
        .table("api_keys")
        .select("user_email")
        # .eq("id", api_key_id)
        .execute()
    )

    if not key_resp.data:
        return {"error": "API key not found"}

    user_email = key_resp.data[0]["user_email"]

    # 2️⃣ Fetch credential
    cred_resp = (
        supabase
        .table("credentials")
        .select("id, user_email")
        .eq("id", credential_id)
        .execute()
    )

    if not cred_resp.data:
        return {"error": "Credential not found"}

    # 3️⃣ Ownership check (PDF implied)
    if cred_resp.data[0]["user_email"] != user_email:
        return {"error": "You are not allowed to revoke this credential"}

    # 4️⃣ Revoke (soft delete = safest)
    supabase.table("credentials").update({
        "status": "revoked"
    }).eq("id", credential_id).execute()

    return {
        "status": "revoked"
    }




