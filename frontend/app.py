import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="INTYRASENSE", layout="centered")
st.title("🧠 INTYRASENSE")
st.caption("Document-grounded Q&A with explicit summarization")

# ============================================================================
# Session State Initialization
# ============================================================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ============================================================================
# Document Upload Section
# ============================================================================

st.divider()
st.header("📄 Upload Documents")

# File uploader widget for multiple files
uploaded_files = st.file_uploader(
    "Upload PDF / Markdown / Text files",
    type=["pdf", "md", "txt"],
    accept_multiple_files=True
)

# Handle upload and indexing
if st.button("Upload & Index"):
    if not uploaded_files:
        st.warning("Please upload at least one document.")
    else:
        with st.spinner("Uploading and rebuilding index..."):
            # Prepare files for multipart form data
            request_files = [("files", (file.name, file.getvalue())) for file in uploaded_files]
            # Send files to backend
            response = requests.post(f"{BACKEND_URL}/upload", files=request_files,timeout=30)

        if response.status_code == 200:
            st.success("Index rebuilt successfully.")
            # Clear chat history since we have new documents
            st.session_state.chat_history.clear()
        else:
            st.error("Upload failed.")


# ============================================================================
# Document Selection Section
# ============================================================================

st.header("📂 Select Document")

# Initialize with "All Documents" option
available_documents = ["All Documents"]

# Fetch list of uploaded documents from backend
try:
    docs_response = requests.get(f"{BACKEND_URL}/documents")
    if docs_response.status_code == 200:
        available_documents += docs_response.json()["documents"]
except:
    st.warning("Backend not reachable")

# Document selection dropdown
selected_document = st.selectbox("Choose document scope", available_documents)

# ============================================================================
# Document Summarization Section
# ============================================================================

st.divider()
st.header("📝 Summarize Document")

# Summarize button
if st.button("Summarize Document"):
    # Validation: Cannot summarize all documents at once
    if selected_document == "All Documents":
        st.warning("Please select a single document to summarize.")
    else:
        # Show loading indicator during summarization
        with st.spinner("Generating summary..."):
            response = requests.post(
                f"{BACKEND_URL}/summarize",
                json={"document": selected_document}
            )

        # Display results
        if response.status_code == 200:
            data = response.json()

            # Display summary
            st.subheader("Summary")
            st.write(data["summary"])

            # Display citations if available
            if data.get("citations"):
                st.subheader("📌 Citations")
                for citation in data["citations"]:
                    st.markdown(f"- `{citation}`")
        else:
            st.error("Summarization failed.")

# ============================================================================
# Question Answering Chat Section
# ============================================================================

st.divider()
st.header("💬 Ask Questions (Strict RAG)")

# Display chat history
# Shows previous question-answer pairs to provide conversation context
for question, answer in st.session_state.chat_history:
    st.chat_message("user").write(question)
    st.chat_message("assistant").write(answer)

user_question = st.chat_input("Ask a fact-based question about the document")

# Handle new question
if user_question:
    st.chat_message("user").write(user_question)

    # Prepare request payload
    payload = {
        "question": user_question,
        "chat_history": st.session_state.chat_history,
        "document": None if selected_document == "All Documents" else selected_document
    }

    # Query backend
    with st.spinner("Searching documents..."):
        response = requests.post(f"{BACKEND_URL}/query", json=payload)

    # Process response
    if response.status_code == 200:
        data = response.json()
        answer_text = data["answer"]
        confidence_score = data.get("confidence", 0.0)
    else:
        answer_text = "Error querying backend."
        confidence_score = 0.0


    st.chat_message("assistant").write(answer_text)
    st.caption(f"🔎 Confidence score: **{confidence_score}**")
    st.caption(
        "ℹ️ Lower confidence indicates dispersed or weak evidence across documents, "
        "not necessarily an incorrect answer."
    )

    st.session_state.chat_history.append((user_question, answer_text))
