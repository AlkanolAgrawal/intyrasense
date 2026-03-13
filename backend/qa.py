from langchain_core.messages import HumanMessage

from backend.models import llm
from backend.supabase_client import supabase
from backend.retriever import retrieve_with_score
from backend.prompts import SYSTEM_PROMPT, SUMMARY_PROMPT


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
def answer_question(question: str, chat_history: list, document: str | None):

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

    # limit to top chunks
    retrieved = retrieved[:5]

    context_chunks = []
    similarities = []
    citations = []

    for row in retrieved:

        content = row.get("content")
        similarity = row.get("similarity", 0)
        doc_name = row.get("document_name")

        if content:
            context_chunks.append(content)
            similarities.append(similarity)

        if doc_name:
            citations.append(doc_name)

    if not context_chunks:
        return {
            "answer": "Not found in internal documents.",
            "citations": [],
            "confidence": 0.0
        }

    # compute confidence
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
def summarize_documents(document: str | None = None):

    query = supabase.table("chunks").select(
        "content, document_name"
    )

    if document:
        query = query.eq("document_name", document)

    response = query.execute()

    if not response.data:
        return {
            "summary": "Not found in internal documents.",
            "citations": []
        }

    # extract chunks
    chunks = [
        row["content"]
        for row in response.data
        if row.get("content")
    ]

    if not chunks:
        return {
            "summary": "Not found in internal documents.",
            "citations": []
        }

    # limit context size (important for speed)
    chunks = chunks[:15]

    context = "\n\n".join(chunks)

    prompt = SUMMARY_PROMPT.format(context=context)

    result = llm().invoke(prompt)

    citations = list({
        row["document_name"]
        for row in response.data
        if row.get("document_name")
    })

    return {
        "summary": result.content.strip(),
        "citations": citations
    }