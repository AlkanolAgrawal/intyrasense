import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="INTYRASENSE", layout="centered")
st.title("🧠 INTYRASENSE")
st.caption("Document-grounded Q&A with explicit evidence")

# ============================================================================
# Session State
# ============================================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ============================================================================
# Upload Section
# ============================================================================

st.divider()
st.header("📄 Upload Documents")

uploaded_files = st.file_uploader(
    "Upload PDF / Markdown / Text files",
    type=["pdf", "md", "txt"],
    accept_multiple_files=True
)

if st.button("Upload & Index"):
    if not uploaded_files:
        st.warning("Please upload at least one document.")
    else:
        with st.spinner("Uploading and rebuilding index..."):
            request_files = [
                ("files", (file.name, file.getvalue()))
                for file in uploaded_files
            ]
            response = requests.post(
                f"{BACKEND_URL}/upload",
                files=request_files,
                timeout=60
            )

        if response.status_code == 200:
            st.success("Index rebuilt successfully.")
            st.session_state.chat_history.clear()
        else:
            st.error("Upload failed.")

# ============================================================================
# Document Selection
# ============================================================================

st.header("📂 Select Document")

available_documents = ["All Documents"]

try:
    docs_response = requests.get(f"{BACKEND_URL}/documents")
    if docs_response.status_code == 200:
        available_documents += docs_response.json()["documents"]
except:
    st.warning("Backend not reachable")

selected_document = st.selectbox(
    "Choose document scope to query or summarise:",
    available_documents
)

# ============================================================================
# Summarization
# ============================================================================

st.divider()
st.header("📝 Summarize Document")

if st.button("Summarize Document"):
    if selected_document == "All Documents":
        st.warning("Please select a single document.")
    else:
        with st.spinner("Generating summary..."):
            response = requests.post(
                f"{BACKEND_URL}/summarize",
                json={"document": selected_document}
            )

        if response.status_code == 200:
            data = response.json()

            st.subheader("Summary")
            st.write(data["summary"])

            if data.get("citations"):
                st.subheader("📌 Citations")
                for citation in data["citations"]:
                    st.markdown(f"- `{citation}`")
        else:
            st.error("Summarization failed.")

# ============================================================================
# Strict RAG Chat
# ============================================================================

st.divider()
st.header("💬 Ask Questions (Strict RAG)")

# Display history
for question, answer in st.session_state.chat_history:
    st.chat_message("user").write(question)
    st.chat_message("assistant").write(answer)

user_question = st.chat_input("Ask a fact-based question about the document")

if user_question:
    st.chat_message("user").write(user_question)

    payload = {
        "question": user_question,
        "chat_history": st.session_state.chat_history,
        "document": None if selected_document == "All Documents" else selected_document
    }

    with st.spinner("Searching documents..."):
        response = requests.post(f"{BACKEND_URL}/query", json=payload)

    if response.status_code == 200:
        data = response.json()
        answer_text = data.get("answer", "No answer returned.")
        confidence_score = data.get("confidence", 0.0)
        evidence = data.get("evidence", [])
    else:
        answer_text = "Error querying backend."
        confidence_score = 0.0
        evidence = []

    st.chat_message("assistant").write(answer_text)
    st.caption(f"🔎 Confidence score: **{confidence_score:.2f}**")

    # Evidence Transparency
    if evidence:
        with st.expander("🔍 Retrieved Evidence"):
            for item in evidence:
                st.markdown(f"**Source:** {item['source']}")
                st.markdown(f"**Score:** {item['score']}")
                st.code(item["content"])
                st.markdown("---")

    st.session_state.chat_history.append((user_question, answer_text))