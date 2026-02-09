# 🧠 INTYRASENSE

**INTYRASENSE** is a Retrieval-Augmented Generation (RAG) system that provides document-grounded question answering and summarization. The system maintains strict adherence to source documents, never hallucinating or using external knowledge.

## ✨ Features

- 📄 **Multi-Format Document Support**: Upload and process PDF, Markdown, and text files
- 🔍 **Semantic Search**: Uses sentence transformers and FAISS for efficient vector similarity search
- 💬 **Context-Aware Q&A**: Maintains chat history and rewrites follow-up questions for better context
- 📝 **Document Summarization**: Generate concise summaries of uploaded documents
- 🎯 **Confidence Scoring**: Each answer includes a confidence score based on retrieval quality
- 📌 **Source Citations**: All answers include references to source documents and page numbers
- 🔒 **Strict RAG**: Only answers from document content, explicitly states when information is not found
- 🔄 **Document Filtering**: Query specific documents or search across all uploaded files

## 🏗️ Architecture

### Backend (FastAPI)
- **main.py**: FastAPI server with upload, query, and summarization endpoints
- **ingest.py**: Document loading, chunking, and FAISS index creation
- **qa.py**: Question answering and summarization logic using LangChain
- **retriever.py**: Vector store retrieval with optional document filtering
- **prompts.py**: System prompts for Q&A and summarization
- **utils.py**: Helper functions for document management

### Frontend (Streamlit)
- **app.py**: Interactive web interface for document upload, Q&A, and summarization

### Data Storage
- **data/raw_docs/**: Stores uploaded documents
- **data/faiss_index/**: Vector embeddings index for semantic search

## 🔧 Technology Stack

- **FastAPI**: Backend REST API
- **Streamlit**: Frontend web interface
- **LangChain**: RAG orchestration framework
- **FAISS**: Facebook AI Similarity Search for vector storage
- **HuggingFace**: Sentence transformers for embeddings (all-MiniLM-L6-v2)
- **Groq**: LLM inference (llama-3.1-8b-instant)
- **PyPDF**: PDF document parsing
- **Unstructured**: Markdown and text processing

## 📋 Prerequisites

- Python 3.8+
- Groq API key (for LLM inference)

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd intyrasense
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

## 🎯 Usage

### Starting the Application

1. **Start the backend server**:
   ```bash
   uvicorn backend.main:app --reload
   ```
   The API will be available at `http://127.0.0.1:8000`

2. **Start the frontend** (in a new terminal):
   ```bash
   streamlit run frontend/app.py
   ```
   The web interface will open at `http://localhost:8501`

### Using the Interface

1. **Upload Documents**:
   - Click "Browse files" to select PDF, Markdown, or text files
   - Click "Upload & Index" to process and index the documents
   - Wait for the indexing process to complete

2. **Ask Questions**:
   - Type your question in the chat input
   - The system will search the documents and provide an answer with:
     - The answer text
     - Source citations (document and page number)
     - Confidence score (0.0 to 1.0)

3. **Summarize Documents**:
   - Select a specific document from the dropdown
   - Click "Summarize Document" to generate a summary
   - View the summary with source citations

4. **Document Filtering**:
   - Use the "Select Document" dropdown to filter queries
   - Choose "All Documents" to search across all files
   - Select a specific document to limit the search scope

## 🔌 API Endpoints

### POST `/upload`
Upload and index documents.

**Request**:
- Form data with `files` (multipart/form-data)
- Accepts: PDF, Markdown (.md), Text (.txt)

**Response**:
```json
{
  "status": "Index rebuilt successfully"
}
```

### POST `/query`
Ask questions about documents.

**Request**:
```json
{
  "question": "What is the main topic?",
  "chat_history": [["Previous question", "Previous answer"]],
  "document": "filename.pdf"  // optional, null for all documents
}
```

**Response**:
```json
{
  "answer": "The answer text based on document content",
  "citations": ["filename.pdf | page 5"],
  "confidence": 0.85
}
```

### POST `/summarize`
Generate document summary.

**Request**:
```json
{
  "document": "filename.pdf"  // optional
}
```

**Response**:
```json
{
  "summary": "Document summary text",
  "citations": ["filename.pdf | page 1", "filename.pdf | page 2"]
}
```

### GET `/documents`
List all uploaded documents.

**Response**:
```json
{
  "documents": ["doc1.pdf", "doc2.md", "doc3.txt"]
}
```

## 📊 How It Works

### Document Ingestion Pipeline
1. **Upload**: Documents are saved to `data/raw_docs/`
2. **Loading**: Documents are loaded using appropriate loaders (PyPDF, TextLoader, etc.)
3. **Chunking**: Text is split into overlapping chunks (800 chars, 100 char overlap)
4. **Embedding**: Chunks are embedded using sentence transformers
5. **Indexing**: Embeddings are stored in FAISS vector database

### Question Answering Pipeline
1. **Question Rewriting**: Follow-up questions are rewritten using chat history for context
2. **Retrieval**: Top-k most similar document chunks are retrieved from FAISS
3. **Confidence Calculation**: Average similarity distance is converted to confidence score
4. **Answer Generation**: LLM generates answer using retrieved context and strict system prompt
5. **Citation Extraction**: Source documents and page numbers are extracted from metadata

### Confidence Scoring
```
confidence = max(0.0, min(1.0, 1 / (1 + average_distance)))
```
- Higher confidence (closer to 1.0) = more relevant retrieved chunks
- Lower confidence (< 0.25) = answer rejected, returns "Not found"
- Confidence reflects retrieval quality, not answer correctness

## 🔒 Design Principles

### Strict RAG Approach
- **No External Knowledge**: System only uses uploaded document content
- **Explicit Uncertainty**: Clearly states when information is not found
- **No Hallucination**: Refuses to guess or make up information
- **Source Attribution**: All answers include citations to source documents

### Privacy & Security
- All processing happens locally (except LLM API calls to Groq)
- Documents are stored locally in `data/` directory
- No data is permanently stored on external servers

## 🛠️ Configuration

### Embedding Model
Change in [retriever.py](backend/retriever.py) and [ingest.py](backend/ingest.py):
```python
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
```

### LLM Model
Change in [qa.py](backend/qa.py):
```python
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0
)
```

### Chunk Size
Change in [ingest.py](backend/ingest.py):
```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100
)
```

### Retrieval Count
Change in [retriever.py](backend/retriever.py):
```python
search_kwargs={"k": 4}  # Number of chunks to retrieve
```

## 📁 Project Structure

```
intyrasense/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (API keys)
├── backend/                  # Backend API
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── ingest.py            # Document processing & indexing
│   ├── qa.py                # Q&A and summarization logic
│   ├── retriever.py         # Vector store retrieval
│   ├── prompts.py           # System prompts
│   └── utils.py             # Helper functions
├── frontend/                 # Frontend UI
│   └── app.py               # Streamlit application
└── data/                     # Data storage
    ├── raw_docs/            # Uploaded documents
    └── faiss_index/         # Vector embeddings index
```

## 🐛 Troubleshooting

### "Backend not reachable"
- Ensure backend is running: `uvicorn backend.main:app --reload`
- Check that it's running on `http://127.0.0.1:8000`

### "Not found in internal documents"
- Verify documents are uploaded and indexed
- Check confidence score - may need better matching documents
- Try rephrasing your question

### Import errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Activate your virtual environment

### Low confidence scores
- Upload more relevant documents
- Try more specific questions
- Check document quality and relevance

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📄 License

This project is provided as-is for educational and commercial use.

## 🙏 Acknowledgments

- Built with [LangChain](https://langchain.com/)
- Powered by [Groq](https://groq.com/) LLM inference
- Uses [FAISS](https://github.com/facebookresearch/faiss) for vector search
- Embeddings from [Sentence Transformers](https://www.sbert.net/)

---

**Made with ❤️ for accurate, source-grounded information retrieval**
