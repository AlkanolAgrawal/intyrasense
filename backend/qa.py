from langchain_core.messages import HumanMessage
from backend.utils import get_doc_id_from_name
from backend.models import llm
from backend.supabase_client import supabase
from backend.retriever import retrieve_with_score
from backend.prompts import SYSTEM_PROMPT, SUMMARY_PROMPT


# ---------------------------------
# HELPER: GET DOCUMENT NAME
# ---------------------------------
def get_document_name(doc_id):

    try:
        res = (
            supabase.table("documents")
            .select("name")
            .eq("id", doc_id)
            .single()
            .execute()
        )

        if res.data:
            return res.data["name"]

    except Exception:
        pass

    return "unknown"


# ---------------------------------
# QUESTION REWRITE
# ---------------------------------
def rewrite_question(chat_history, question):

    if not chat_history:
        return question.strip()

    history = "\n".join(
        f"Q: {q}\nA: {a}" for q, a in chat_history[-3:]
    )

    prompt = f"""
Rewrite the follow-up question so it is fully self-contained.

Conversation:
{history}

Follow-up question:
{question}

Standalone question:
"""

    response = llm().invoke(prompt)

    return response.content.strip()


# ---------------------------------
# RAG QUESTION ANSWERING
# ---------------------------------
def answer_question(question: str, chat_history: list, document=None):
    standalone_question = rewrite_question(chat_history, question)
    doc_id = get_doc_id_from_name(document)

    retrieved = retrieve_with_score(
        standalone_question,
        doc_id
    )

    if not retrieved:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    retrieved = retrieved[:5]
    print("SCORES:", [row.get("score") for row in retrieved])
    context_chunks = []
    similarities = []
    citations = []

    for row in retrieved:

        content = row.get("text")
        similarity = row.get("score", 0)
        doc_id = row.get("source")
        page = row.get("page")

        if content:
            context_chunks.append(content)
            if isinstance(similarity, (int, float)):
                similarities.append(similarity)

        if doc_id:
            book_name = get_document_name(doc_id)
            
            if not book_name or book_name == "unknown":
                continue
            parts = [book_name]
            if isinstance(page, int) and page > 0:
                parts.append(f"page {page}")
            citations.append(" — ".join(parts))

    if not context_chunks:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    # confidence score
    if not similarities:
        confidence = 0.0
    else:
        confidence = max(similarities)
        confidence = max(0.0, min(1.0, float(confidence)))

    if confidence < 0.2:
        print("neeche wala confidence")
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": round(confidence, 2)
        }

    # build context
    context = "\n\n".join(context_chunks)
    prompt = SYSTEM_PROMPT.format(
        context=context,
        question=standalone_question
    )

    response = llm().invoke(prompt)

    return {
        "answer": response.content.strip(),
        "citations": list(set(citations)),
        "confidence": round(confidence, 2)
    }


# ---------------------------------
# DOCUMENT SUMMARIZATION
# ---------------------------------

def summarize_documents(document=None):
    print("Summarizing document:", document)
    query = supabase.table("chunks").select(
        "text, source"
    )
    if document:
        doc_id = get_doc_id_from_name(document)
        if not doc_id:
            return {
                "summary": "Document not found.",
                "citations": []
            }
            
        query = query.eq("source", doc_id)       
    response = query.limit(15).execute() # limit context for LLM
    

    if not response.data:
        return {
            "summary": "Not found in internal documents.",
            "citations": []
        }

    chunks = [
        row["text"]
        for row in response.data
        if row.get("text")
    ]

    if not chunks:
        return {
            "summary": "Not found in internal documents.",
            "citations": []
        }

    
    context = "\n\n".join(chunks)
    prompt = SUMMARY_PROMPT.format(context=context)

    result = llm().invoke(prompt)

    citations = []

    for row in response.data:
        if row.get("source"):
            citations.append(get_document_name(row["source"]))

    return {
        "summary": result.content.strip(),
        "citations": list(set(citations))
    }