import streamlit as st
import requests
import os
import time
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="INTYRASENSE", layout="centered")
st.title("🧠 INTYRASENSE")
st.caption("Document-grounded Q&A with explicit evidence")

# ==============================
# SESSION STATE
# ==============================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ==============================
# HELPER: FETCH DOCUMENTS
# ==============================

@st.cache_data(ttl=30)
def get_documents():
    try:
        r = requests.get(f"{BACKEND_URL}/documents", timeout=5)
        if r.status_code == 200:
            return r.json().get("documents", [])
    except:
        pass
    return []

# ==============================
# UPLOAD SECTION
# ==============================

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
        st.stop()
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    valid_files = []


    for f in uploaded_files:
        if f.size > MAX_FILE_SIZE:
            st.error(f"{f.name} exceeds 50MB limit.")
        else:
            valid_files.append(f)

    if not valid_files:
        st.stop()

    try:
        with st.spinner("Uploading and indexing documents..."):

            files_payload = [
                ("files", (f.name, f.getvalue(), "application/octet-stream"))
                for f in valid_files
            ]

            r = requests.post(
                f"{BACKEND_URL}/upload",
                files=files_payload,
                timeout=120
            )

        if r.status_code == 200:

            data = r.json()

            st.success("Documents uploaded successfully.")
            st.info(data.get("message", "Chunk ingestion started."))

            status_box = st.empty()

            while True:

                try:
                    res = requests.get(
                        f"{BACKEND_URL}/ingestion-status",
                        timeout=5
                    )

                    if res.status_code == 200:

                        state = res.json().get("state")

                        if state == "running":
                            status_box.info("Indexing document chunks...")

                        elif state == "completed":
                            status_box.success(
                                "✔ All document chunks ingested successfully."
                            )
                            break

                        elif state == "failed":
                            status_box.error("Ingestion failed.")
                            break

                except:
                    status_box.warning("Checking ingestion status...")

                time.sleep(2)

            st.session_state.chat_history.clear()
            get_documents.clear()

        else:
            st.error(r.text)
    except requests.exceptions.RequestException:
        st.error("Backend not reachable.")


# ==============================
# DOCUMENT SELECTION
# ==============================

st.divider()
st.header("📂 Select Document")
docs = get_documents()
# print("Fetched documents:", docs)
doc_map = {}
for d in docs:
    doc_map[d["name"]] = d["storage_path"] 

options = ["All Documents"] + list(doc_map.keys())

selected_name = st.selectbox(
    "Choose document scope:",
    options
)
# print(doc_map)
selected_document = None
if selected_name != "All Documents":
    selected_document = doc_map[selected_name]
print("Selected document path:", selected_document)
# ==============================
# SUMMARIZATION
# ==============================

st.divider()
st.header("📝 Summarize Document")
if st.button("Summarize Document"):

    if selected_document == "All Documents":
        st.warning("Please select a single document.")
        st.stop()

    try:
        with st.spinner("Generating summary..."):
            print("Selected document:", selected_document)
            r = requests.post(
                f"{BACKEND_URL}/summarize",
                json={"document": selected_document}, #doc_id gone
                timeout=60
            )
        if r.status_code == 200:

            data = r.json()

            st.subheader("Summary")
            st.write(data.get("summary", ""))

            citations = data.get("citations", [])

            if citations:
                st.subheader("📌 Citations")
                for c in citations:
                    st.markdown(f"- `{c}`")

        else:
            st.error(r.text)

    except requests.exceptions.RequestException:
        st.error("Backend not reachable.")


# ==============================
# CHAT
# ==============================

st.divider()
st.header("💬 Ask Questions")

if st.button("Clear Chat"):
    st.session_state.chat_history.clear()
    st.rerun()


# display history
for q, a in st.session_state.chat_history:
    st.chat_message("user").write(q)
    st.chat_message("assistant").write(a)


user_question = st.chat_input("Ask a question about the documents")

if user_question:

    st.chat_message("user").write(user_question)

    payload = {
        "question": user_question,
        "chat_history": st.session_state.chat_history,
        "document": None if selected_document == "All Documents" else selected_document
    }

    try:
        with st.spinner("Searching documents..."):

            r = requests.post(
                f"{BACKEND_URL}/query",
                json=payload,
                timeout=60
            )

        if r.status_code == 200:

            data = r.json()

            answer = data.get("answer", "No answer returned.")
            confidence = data.get("confidence", 0.0)
            citations = data.get("citations", [])

        else:
            answer = "Backend error."
            confidence = 0
            citations = []

    except requests.exceptions.RequestException:
        answer = "Backend not reachable."
        confidence = 0
        citations = []

    st.chat_message("assistant").write(answer)
    st.caption(f"🔎 Confidence: **{confidence:.2f}**")

    if citations:
        with st.expander("Sources"):
            for c in citations:
                st.markdown(f"- `{c}`")

    st.session_state.chat_history.append((user_question, answer))