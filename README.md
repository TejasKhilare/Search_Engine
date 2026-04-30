# 🔍 AI-Powered Document Search Engine (RAG + Semantic Search)

A full-stack AI application that enables users to upload documents, perform semantic search, and get context-aware answers using Retrieval-Augmented Generation (RAG).

---

## 🚀 Features

### 🔐 Authentication
- User registration & login (JWT-based)
- Protected routes (frontend + backend)

### 📂 Document Management
- Upload PDF documents
- Background processing (chunking + embeddings)
- Real-time status updates (polling)
- Delete documents

### 🔎 Semantic Search
- Vector-based search using embeddings
- Retrieve relevant document chunks
- Auto-load top result document
- Page-level PDF rendering

### 📄 PDF Viewer + Highlighting
- Render PDF using `react-pdf`
- Highlight matched content dynamically
- Page navigation based on search results

### 🤖 AI Search (RAG)
- Ask natural language questions
- Context-aware answer generation
- Sources linked to document chunks

---

## 🧠 Tech Stack

### Frontend
- React (Vite)
- Tailwind CSS
- Zustand (state management)
- React Router
- Axios
- React-PDF

### Backend
- FastAPI
- PostgreSQL (SQLAlchemy ORM)
- Qdrant (Vector DB)
- Gemini API (Embeddings)
- OpenAI (LLM for RAG)

### Infrastructure
- Docker (API + DB + Vector Store)

---

