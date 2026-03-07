from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain_huggingface import HuggingFaceEmbeddings

from backend.ingest import INDEX_DIR
from backend.retriever import retrieve_with_score
from backend.prompts import SYSTEM_PROMPT, SUMMARY_PROMPT


def rewrite_question(chat_history, question, llm):
    if not chat_history:
        return question.strip()

    # Build context from the last 3 Q&A pairs
    history_context = ""
    for past_question, past_answer in chat_history[-3:]:
        history_context += f"Q: {past_question}\nA: {past_answer}\n"

    rewrite_prompt = f"""
Rewrite the follow-up question so it is fully self-contained.

Conversation:
{history_context}

Follow-up question:
{question}

Standalone question:
"""

    response = llm.invoke([HumanMessage(content=rewrite_prompt)])
    return response.content.strip()


def answer_question(question: str, chat_history: list, selected_document: str | None):
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0
    )

    # Rewrite follow-up questions to be standalone
    standalone_question = rewrite_question(chat_history, question, llm)

    # Retrieve relevant document chunks with similarity scores
    retrieval_results = retrieve_with_score(
        standalone_question,
        selected_document
    )

    # Handle case where no documents are retrieved
    if not retrieval_results:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    # Separate documents and their similarity scores
    retrieved_docs = []
    similarity_scores = []

    for doc, score in retrieval_results:
        retrieved_docs.append(doc)
        similarity_scores.append(score)

    # confidence score
    average_distance = sum(similarity_scores) / len(similarity_scores)
    confidence = float(max(0.0, min(1.0, 1 / (1 + average_distance))))
    
    # Reject low confidence answers 
    if confidence < 0.25:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": round(confidence, 2)
        }

    # Build context from retrieved documents
    context_text = ""
    citation_set = set()

    for doc in retrieved_docs:
        text = doc.page_content.strip()
        
        # Filter out very short chunks (likely noise)
        if len(text) < 20:
            continue
            
        context_text += text + "\n\n"
        
        # Extract citation information from metadata
        source_file = doc.metadata.get("source", "unknown")
        page_number = doc.metadata.get("page", "N/A")
        citation_set.add(f"{source_file} | page {page_number}")

    # Empty context fallback
    if not context_text.strip():
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    # Generate answer using LLM with strict system prompt
    final_prompt = SYSTEM_PROMPT.format(
        context=context_text,
        question=question
    )

    llm_response = llm.invoke([HumanMessage(content=final_prompt)])
    final_answer = llm_response.content.strip()

    return {
        "answer": final_answer,
        "citations": list(citation_set),
        "confidence": round(confidence, 2)
    }
def summarize_documents(selected_document: str | None = None):
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0
    )

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    db = FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

    # Collect ALL chunks of the selected document
    all_chunks = [
        doc for doc in db.docstore._dict.values()
        if doc.metadata.get("source") == selected_document
    ]

    if not all_chunks:
        return {
            "summary": "Not found in internal documents.",
            "citations": []
        }

    # ---- Small Document: Direct Summary ----
    full_text = "\n\n".join(doc.page_content for doc in all_chunks)

    if len(full_text) < 6000:  # safe threshold for context window
        final_prompt = SUMMARY_PROMPT.format(context=full_text)
        response = llm.invoke([HumanMessage(content=final_prompt)])

        citations = {
            f"{doc.metadata.get('source')} | page {doc.metadata.get('page', 'N/A')}"
            for doc in all_chunks
        }

        return {
            "summary": response.content.strip(),
            "citations": list(citations)
        }

    # ---- Large Document: Hierarchical Summarization ----
    partial_summaries = []

    for doc in all_chunks:
        prompt = SUMMARY_PROMPT.format(context=doc.page_content)
        response = llm.invoke([HumanMessage(content=prompt)])
        partial_summaries.append(response.content)

    combined_text = "\n".join(partial_summaries)

    final_prompt = SUMMARY_PROMPT.format(context=combined_text)
    final_response = llm.invoke([HumanMessage(content=final_prompt)])

    citations = {
        f"{doc.metadata.get('source')} | page {doc.metadata.get('page', 'N/A')}"
        for doc in all_chunks
    }

    return {
        "summary": final_response.content.strip(),
        "citations": list(citations)
    }