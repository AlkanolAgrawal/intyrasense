from langchain_core.messages import HumanMessage

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
    if document:
        document = document.split("_",1)[0]

    standalone_question = rewrite_question(chat_history, question)

    retrieved = retrieve_with_score(
        standalone_question,
        document
    )

    if not retrieved:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    retrieved = retrieved[:5]

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
            similarities.append(similarity)

        if doc_id:
            book_name = get_document_name(doc_id)
            citations.append(f"{book_name} (page {page})")

    if not context_chunks:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    # confidence score
    confidence = sum(similarities) / len(similarities)
    confidence = max(0.0, min(1.0, float(confidence)))

    if confidence < 0.25:
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
   
    if document and "_" in document:
        document = document.split("_",1)[0]
    print("Summarizing document:", document)
    query = supabase.table("chunks").select(
        "text, source"
    )

    if document:
        query = query.eq("source", document)

    response = query.execute()

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

    # limit context for LLM
    chunks = chunks[:15]

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