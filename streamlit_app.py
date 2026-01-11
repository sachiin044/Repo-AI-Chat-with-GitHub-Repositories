import streamlit as st
import requests
import uuid

# ------------------ CONFIG ------------------
BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="RepoLens",
    layout="wide"
)

st.title("🤖 RepoLens — Chat with GitHub Repositories")

# ------------------ SESSION STATE ------------------

# Unique session id for memory (Lesson 8 requirement)
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Chat history for UI only (LLM memory is server-side)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Repo indexing flag
if "repo_indexed" not in st.session_state:
    st.session_state.repo_indexed = False

# ------------------ BACKEND CALL HELPER ------------------
def call_backend(endpoint: str, payload: dict):
    try:
        response = requests.post(
            f"{BACKEND_URL}{endpoint}",
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            st.error(f"Backend error: {response.status_code}")
            return None

        return response.json()

    except requests.exceptions.ConnectionError:
        st.error("❌ Backend is not running. Start FastAPI on port 8000.")
        st.stop()

    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None


# ------------------ INDEX REPOSITORY ------------------
st.header("1️⃣ Index a GitHub Repository")

repo_url = st.text_input(
    "Repository URL",
    placeholder="https://github.com/tiangolo/fastapi"
)

if st.button("Index Repository"):
    if repo_url.strip() == "":
        st.warning("Please enter a GitHub repository URL.")
    else:
        with st.spinner("Cloning and indexing repository..."):
            result = call_backend(
                "/upload-repo",
                {"repo_url": repo_url}
            )

        if result:
            st.success("✅ Repository indexed successfully.")
            st.session_state.repo_indexed = True

st.divider()

# ------------------ ASK QUESTION ------------------
st.header("2️⃣ Ask a Question")

question = st.text_input(
    "Your question",
    placeholder="What does ingest.py do?"
)

if st.button("Ask"):
    if not st.session_state.repo_indexed:
        st.warning("Please index a repository first.")
    elif question.strip():
        with st.spinner("Thinking..."):
            result = call_backend(
                "/chat",
                {
                    "question": question,
                    "session_id": st.session_state.session_id
                }
            )

        if result and "answer" in result:
            st.session_state.chat_history.append({
                "question": question,
                "answer": result["answer"],
                "follow_ups": result.get("follow_ups", [])
            })
        else:
            st.error("Invalid response from backend.")

st.divider()

# ------------------ CHAT HISTORY ------------------
st.header("💬 Conversation")

for idx, chat in enumerate(reversed(st.session_state.chat_history)):
    st.markdown("### 🧑 You")
    st.markdown(chat["question"])

    st.markdown("### 🤖 RepoLens")
    st.markdown(chat["answer"])

    follow_ups = chat.get("follow_ups", [])

    if follow_ups:
        st.markdown("**🔁 Follow-up questions:**")
        for fq in follow_ups:
            if st.button(f"➡️ {fq}", key=f"{idx}-{fq}"):
                with st.spinner("Thinking..."):
                    result = call_backend(
                        "/chat",
                        {
                            "question": fq,
                            "session_id": st.session_state.session_id
                        }
                    )

                if result and "answer" in result:
                    st.session_state.chat_history.append({
                        "question": fq,
                        "answer": result["answer"],
                        "follow_ups": result.get("follow_ups", [])
                    })
                    st.rerun()
                else:
                    st.error("Failed to fetch follow-up response.")

    st.markdown("---")
