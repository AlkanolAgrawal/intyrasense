import os
from functools import lru_cache
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings


# -----------------------------
# LOAD ENV
# -----------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set")


# -----------------------------
# LLM
# -----------------------------
@lru_cache(maxsize=1)
def llm():
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=GROQ_API_KEY
    )


# -----------------------------
# EMBEDDINGS
# -----------------------------
@lru_cache(maxsize=1)
def embeddings():
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={
            "normalize_embeddings": True
        }
    )