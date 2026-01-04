# streamlit_app.py
import streamlit as st
import requests

# ------------------ CONFIG ------------------
BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Repo AI",
    layout="wide"
)

st.title("🤖 Repo AI — Chat with GitHub Repositories")

# ------------------ SESSION STATE ------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "repo_indexed" not in st.session_state:
    st.session_state.repo_indexed = False

# ------------------ SAFE BACKEND CALL ------------------
def call_backend(endpoint, payload):
    try:
        response = requests.post(
            f"{BACKEND_URL}{endpoint}",
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            st.error(f"Backend error: {response.status_code}")
            return None

        data = response.json()
        if not isinstance(data, dict):
            return None

        return data

    except requests.exceptions.ConnectionError:
        st.error("❌ Backend is not running. Please start FastAPI on port 8000.")
        st.stop()

    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

# ------------------ REPO INDEXING ------------------
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
    placeholder="What is good in this repository?"
)

if st.button("Ask"):
    if not st.session_state.repo_indexed:
        st.warning("Please index a repository first.")
    elif question.strip():
        with st.spinner("Thinking..."):
            result = call_backend(
                "/chat",
                {"question": question}
            )

        if not result:
            st.error("Invalid response from backend.")
        elif "answer" not in result:
            st.error(result.get("error", "No answer returned."))
        else:
            st.session_state.chat_history.append({
                "question": question,
                "answer": result["answer"],
                "follow_ups": result.get("follow_ups", [])
            })

st.divider()

# ------------------ CHAT HISTORY ------------------
st.header("💬 Conversation")

for idx, chat in enumerate(reversed(st.session_state.chat_history)):
    st.markdown("### 🧑 You")
    st.markdown(chat["question"])

    st.markdown("### 🤖 Repo AI")
    st.markdown(chat["answer"])

    follow_ups = chat.get("follow_ups") or []

    if follow_ups:
        st.markdown("**🔁 Follow-up questions:**")
        for fq in follow_ups:
            if st.button(f"➡️ {fq}", key=f"{idx}-{fq}"):
                with st.spinner("Thinking..."):
                    result = call_backend(
                        "/chat",
                        {"question": fq}
                    )

                if not result or "answer" not in result:
                    st.error("Failed to fetch follow-up response.")
                    st.stop()

                st.session_state.chat_history.append({
                    "question": fq,
                    "answer": result["answer"],
                    "follow_ups": result.get("follow_ups", [])
                })

                # Proper rerun (stable API)
                st.rerun()

    st.markdown("---")
