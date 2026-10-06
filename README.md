# Conversational RAG Backend

A FastAPI backend for document-based question answering and conversational interview scheduling.

The project was built as a backend-focused implementation of a custom RAG system. It supports PDF/TXT ingestion, multiple chunking strategies, embeddings with Qdrant, PostgreSQL metadata storage, Redis-based conversation memory, multi-turn queries, and LLM-powered interview booking.

## Features

### Document ingestion

* Upload `.pdf` and `.txt` documents through a REST API
* Validate uploaded files before processing
* Extract text from documents
* Support two chunking strategies:

  * `fixed`: fixed-size chunks with overlap
  * `recursive`: paragraph-aware recursive splitting
* Generate embeddings for each chunk
* Store vectors and metadata in Qdrant
* Store document metadata in PostgreSQL
* Detect duplicate files using SHA-256 hashing
* Remove associated vectors when a document is deleted

### Conversational RAG

* Ask questions about uploaded documents through a single chat endpoint
* Support multi-turn conversations
* Rewrite follow-up questions into standalone queries
* Retrieve relevant chunks from Qdrant
* Generate answers using retrieved context
* Return source information with the response
* Optionally restrict retrieval to specific documents

### Interview scheduling

The same chat endpoint can also handle interview booking.

The conversation guides the user through:

1. Name
2. Email
3. Preferred date
4. Preferred time
5. Confirmation

The booking flow validates the collected information, checks for scheduling conflicts, and stores confirmed bookings in PostgreSQL.

### LLM fallback

The application supports a primary LLM with an optional local vLLM fallback.

For example, Gemini can be used as the primary provider while a local Qwen model served through vLLM is used if the primary provider becomes unavailable.

The switch happens inside the backend, so the client does not need to change its request.

### Conversation memory

Redis is used to maintain session-based conversation history.

Memory has configurable:

* Session TTL
* Token/message budget
* Multi-turn context

---

## Architecture

At a high level, the application follows this flow:

```text
                         ┌──────────────────┐
                         │      Client      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     FastAPI      │
                         │    REST APIs     │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
          ┌──────────────────┐        ┌──────────────────┐
          │ Document Ingest  │        │   Chat / RAG     │
          └────────┬─────────┘        └────────┬─────────┘
                   │                           │
                   ▼                           ▼
          ┌──────────────────┐        ┌──────────────────┐
          │ Text Extraction  │        │ Redis Memory     │
          └────────┬─────────┘        └────────┬─────────┘
                   │                           │
                   ▼                           ▼
          ┌──────────────────┐        ┌──────────────────┐
          │    Chunking      │        │ Query Rewriting  │
          └────────┬─────────┘        └────────┬─────────┘
                   │                           │
                   ▼                           ▼
          ┌──────────────────┐        ┌──────────────────┐
          │   Embeddings     │───────►│     Qdrant       │
          └──────────────────┘        │ Vector Retrieval │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │       LLM        │
                                      │ Primary/Fallback │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │ Chat / Booking   │
                                      │     Response     │
                                      └──────────────────┘

          PostgreSQL stores document metadata and bookings.
```

The application keeps the main responsibilities separated into API routes, services, repositories, database models, and schemas.

---

## Tech Stack

| Component           | Technology            |
| ------------------- | --------------------- |
| Language            | Python 3.11           |
| API                 | FastAPI               |
| Database            | PostgreSQL 16         |
| ORM                 | SQLAlchemy 2          |
| Database Driver     | asyncpg               |
| Vector Database     | Qdrant                |
| Conversation Memory | Redis 7               |
| LLM Client          | OpenAI-compatible API |
| Migrations          | Alembic               |
| Package Manager     | uv                    |
| Containerization    | Docker Compose        |
| Testing             | Pytest                |
| Linting             | Ruff                  |
| Type Checking       | Mypy                  |

The LLM layer is provider-independent and can work with services that expose an OpenAI-compatible API.

---

## Getting Started

### Requirements

You will need:

* Python 3.11+
* Docker and Docker Compose
* An API key for the LLM provider you want to use

Using Docker Compose is recommended because PostgreSQL, Redis, Qdrant, and the API can be started together.

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd conversational-rag-backend
```

### 2. Configure environment variables

Create your local environment file:

```bash
cp .env.example .env
```

Then configure the required LLM settings in `.env`.

The project includes configuration examples for providers such as Gemini, OpenAI, Groq, and local models.

### 3. Start the application

```bash
docker compose up --build -d
```

This starts:

* FastAPI
* PostgreSQL
* Redis
* Qdrant

Database migrations are applied during application startup.

The API runs on:

```text
http://localhost:8001
```

The port can be changed through the environment configuration.

### 4. Check the health endpoint

```bash
curl http://localhost:8001/health
```

A healthy response looks like:

```json
{
  "status": "ok",
  "checks": {
    "postgres": "ok",
    "redis": "ok",
    "qdrant": "ok"
  }
}
```

---

# API Usage

## 1. Upload a document

The ingestion endpoint accepts `.pdf` and `.txt` files.

### Recursive chunking

This strategy attempts to preserve paragraph and text boundaries while creating chunks.

```bash
curl -X POST http://localhost:8001/api/v1/documents \
  -F "file=@samples/sample.pdf" \
  -F "chunking_strategy=recursive" \
  -F "chunk_size=400" \
  -F "chunk_overlap=80"
```

### Fixed-size chunking

This strategy creates chunks using a fixed character window with overlap.

```bash
curl -X POST http://localhost:8001/api/v1/documents \
  -F "file=@samples/sample.txt" \
  -F "chunking_strategy=fixed" \
  -F "chunk_size=300" \
  -F "chunk_overlap=50"
```

Each uploaded document is identified using its SHA-256 hash. Uploading the same file again does not create duplicate embeddings.

---

## 2. Ask questions about documents

Send a message to the chat endpoint:

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-001",
    "message": "What is the document ingestion pipeline?"
  }'
```

The backend:

1. Loads the conversation history from Redis.
2. Determines whether the message requires conversational context.
3. Rewrites follow-up questions when necessary.
4. Generates an embedding for the query.
5. Searches Qdrant for relevant chunks.
6. Builds a prompt using the retrieved context.
7. Sends the request to the configured LLM.
8. Stores the conversation in Redis.
9. Returns the answer with source information.

### Multi-turn conversation

The same `session_id` can be reused for follow-up questions:

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-001",
    "message": "Which chunking strategies does it support?"
  }'
```

The previous conversation is available through Redis, allowing the backend to understand follow-up questions.

### Restrict retrieval to specific documents

A request can optionally include document IDs:

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-001",
    "message": "Summarize this document",
    "document_ids": [
      "<document-uuid>"
    ]
  }'
```

---

# Interview Booking

Interview scheduling is handled through the same chat endpoint.

No separate booking flag is required. The backend detects booking intent and moves the conversation into the appropriate booking flow.

### Turn 1: Start booking

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "booking-001",
    "message": "I want to schedule an interview"
  }'
```

### Turn 2: Provide personal details

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "booking-001",
    "message": "My name is Arun Gupta, email garun9006@gmail.com"
  }'
```

### Turn 3: Select a date and time

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "booking-001",
    "message": "2026-11-15 at 14:00"
  }'
```

### Turn 4: Confirm

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "booking-001",
    "message": "confirm"
  }'
```

Before saving a booking, the backend validates the collected information and checks whether the requested time conflicts with an existing booking.

---

# Other Endpoints

### List documents

```bash
curl "http://localhost:8001/api/v1/documents?limit=10&offset=0"
```

### Get document details

```bash
curl http://localhost:8001/api/v1/documents/<document-id>
```

### Delete a document

```bash
curl -X DELETE \
  http://localhost:8001/api/v1/documents/<document-id>
```

Deleting a document also removes its associated vectors from Qdrant.

### List confirmed bookings

```bash
curl "http://localhost:8001/api/v1/bookings?limit=10&offset=0"
```

---

# LLM Configuration

The application uses the standard OpenAI Python client with configurable base URLs. This allows the same LLM service to work with different providers.

| Provider | Base URL                                                  | Example Model             |
| -------- | --------------------------------------------------------- | ------------------------- |
| Gemini   | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash`        |
| OpenAI   | `https://api.openai.com/v1`                               | `gpt-4o-mini`             |
| Groq     | `https://api.groq.com/openai/v1`                          | `llama-3.1-70b-versatile` |
| Ollama   | `http://host.docker.internal:11434/v1`                    | `llama3.1`                |

The exact model and credentials are configured through environment variables rather than being hardcoded in the application.

## Local vLLM fallback

A local vLLM server can be configured as a fallback provider.

For example:

```env
VLLM_BASE_URL=http://host.docker.internal:8002/v1
LOCAL_VLLM_MODEL=Qwen/Qwen2.5-1.5B-Instruct-AWQ
```

If the primary LLM fails or returns a rate-limit error, the fallback service can retry the request using the local vLLM model.

This keeps the client-side API unchanged.

---

# Project Structure

```text
.
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── booking.py
│   │       ├── chat.py
│   │       ├── health.py
│   │       └── ingestion.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── middleware.py
│   │
│   ├── db/
│   │   ├── models.py
│   │   └── session.py
│   │
│   ├── repositories/
│   │
│   ├── schemas/
│   │
│   └── services/
│       ├── booking.py
│       ├── chunking/
│       ├── document_loader.py
│       ├── embeddings.py
│       ├── llm.py
│       ├── memory.py
│       ├── rag.py
│       └── vector_store.py
│
├── alembic/
├── tests/
├── samples/
├── http/
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

### Separation of responsibilities

The project keeps the main application layers separate:

* **Routes** handle HTTP requests and responses.
* **Schemas** define request and response structures.
* **Services** contain application and RAG logic.
* **Repositories** handle PostgreSQL data access.
* **Vector store service** handles Qdrant operations.
* **Memory service** handles Redis conversation state.
* **LLM service** handles model communication and fallback.
* **Database models** define persistent data structures.

This keeps the API layer relatively thin and makes the core logic easier to test and modify.

---

# Testing and Code Quality

Development commands are provided through the `Makefile`.

Install dependencies:

```bash
make install
```

Run tests:

```bash
make test
```

Run linting:

```bash
make lint
```

Run type checking:

```bash
make typecheck
```

The test suite covers the main ingestion, chunking, RAG, booking, and service behavior.

---

# Design Notes

A few design decisions were intentional:

### No LangChain

The RAG pipeline is implemented directly rather than using `RetrievalQAChain`.

This makes the retrieval and generation flow explicit:

```text
User Query
    ↓
Conversation Memory
    ↓
Query Rewriting
    ↓
Embedding
    ↓
Qdrant Retrieval
    ↓
Context Construction
    ↓
LLM
    ↓
Response + Sources
```

### Qdrant instead of an in-process vector store

Qdrant provides a dedicated vector database and keeps vector storage separate from the application process.

### Redis for conversation state

Conversation history is session-based and does not need to be permanently stored in PostgreSQL. Redis also provides TTL support for automatically expiring inactive sessions.

### PostgreSQL for persistent data

Documents, document metadata, and confirmed interview bookings are stored in PostgreSQL so they remain available independently of the Redis session.

---

# Assignment Requirements

The implementation covers the requested backend requirements:

| Requirement             | Implementation                   |
| ----------------------- | -------------------------------- |
| FastAPI backend         | FastAPI                          |
| PDF/TXT ingestion       | `document_loader.py`             |
| Two chunking strategies | Fixed + recursive                |
| Embeddings              | Embedding service                |
| Vector database         | Qdrant                           |
| Metadata database       | PostgreSQL                       |
| Custom RAG              | `rag.py`                         |
| Redis chat memory       | Redis memory service             |
| Multi-turn conversation | Session-based chat               |
| Interview booking       | Booking state machine            |
| Booking persistence     | PostgreSQL                       |
| Type annotations        | Typed Python code                |
| No FAISS                | Not used                         |
| No Chroma               | Not used                         |
| No RetrievalQAChain     | Not used                         |
| Modular architecture    | Routes → Services → Repositories |

---
