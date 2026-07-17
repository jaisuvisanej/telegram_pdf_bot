# TestYourself AI – Telegram AI PDF Study Bot

TestYourself AI is a production-ready, clean-architecture Telegram bot and FastAPI backend application. It allows users to upload PDF documents, extract their contents, index them using vector embeddings (FAISS), and interact with them using Google Gemini AI.

Users can generate summaries, conceptual Q&A sheets, multiple-choice quiz questions (MCQs), flashcards, and interview prep guides, or perform RAG-based conversations.

---

## Key Features

- 👤 **Telegram ID Authentication**: Auto-register and isolate each user's library and database operations using their Telegram User ID.
- 📥 **PDF Extraction & Validation**: Robust text extraction using `PyMuPDF` with file type checks and file size limits.
- 🔍 **Retrieval-Augmented Generation (RAG)**: Splits documents page-by-page, generates embeddings via Google's `text-embedding-004`, and searches with a CPU-friendly `FAISS` vector index. Citations trace back to the exact PDF page.
- 🧩 **Interactive Quiz System**: Inline Telegram keyboard pagination allowing users to flip through multiple-choice questions and reveal answers and reasoning explanations.
- 📦 **Clean Architecture & Scalable Repositories**: Modular design separating the delivery layers (FastAPI REST API, Telegram Bot Interface) from core business logic services and database repositories. Swappable database dialects (SQLite/PostgreSQL) and LLM clients.

---

## Project Structure

```text
testyourself_ai/
├── Dockerfile             # Multi-stage container instructions
├── docker-compose.yml     # Service orchestration (FastAPI + Telegram Bot)
├── requirements.txt       # Dependencies
├── .env.example           # Reference config keys
├── .gitignore
├── README.md              # Technical document
└── src/
    ├── config/            # Pydantic settings & logging configs
    ├── database/          # Connection setups, SQLAlchemy models & repository layer
    ├── models/            # Shared Pydantic schemas (DTO validation)
    ├── pdf/               # PyMuPDF extractor service
    ├── ai/                # LLM base service and Gemini implementation
    ├── rag/               # Chunker, FAISS vector index builder & retriever
    ├── services/          # Core business orchestrators (StudyService & UserService)
    ├── backend/           # FastAPI instance & routes (Health, PDFs, Study)
    └── bot/               # Telegram bot handlers & inline keyboard decorators
```

---

## Getting Started

### 📋 Prerequisites

- Python 3.12+
- Telegram Bot Token (obtained from [@BotFather](https://t.me/BotFather))
- Google Gemini API Key (obtained from Google AI Studio)

---

### 🔧 Manual Local Installation

1. **Clone the repository** and navigate to the project directory:
   ```bash
   cd testyourself_ai
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up configurations**:
   Copy `.env.example` to `.env` and fill in your actual credentials:
   ```bash
   cp .env.example .env
   ```
   *Required settings:*
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token.
   - `GEMINI_API_KEY`: Your Gemini API access key.

---

### 🚀 Running the Application

You can launch the components separately or together using Docker.

#### Run FastAPI Backend locally:
```bash
python -m src.backend.main
```
The interactive Swagger API docs will be active at `http://localhost:8000/docs`.

#### Run Telegram Bot locally:
```bash
python -m src.bot.main
```

---

### 🐳 Running with Docker & docker-compose

This launches both the FastAPI backend and the Telegram Bot as independent microservice containers sharing mapped volumes:

```bash
docker-compose up --build -d
```

- Mapped volumes ensure extracted PDFs (`/app/uploads`) and log files (`/app/logs`) persist across container updates.
- Check service states using:
  ```bash
  docker-compose ps
  ```

---

## API Documentation Summary

### Health
- `GET /health` - Verifies operational status and database connection.

### PDFs
- `POST /api/pdfs/upload` - Accept a PDF file, extract text, builds FAISS indexing.
- `GET /api/pdfs` - Retrieves list of user-owned PDFs.
- `DELETE /api/pdfs/{pdf_id}` - Deletes PDF and removes index binaries.

### Study & AI
- `GET /api/study/summary/{pdf_id}` - Generates/retrieves PDF summaries, core concepts, and ELI10 descriptions.
- `GET /api/study/questions/{pdf_id}?type={MCQ|FLASHCARD|QA|INTERVIEW}` - Compiles study materials.
- `POST /api/study/chat/{pdf_id}` - Submits a question for vector-similarity searches (RAG) and chat response.
- `DELETE /api/study/chat/{pdf_id}` - Clears conversations contexts.

---

## Architectural Choices & Scalability

1. **Service Decoupling (Clean Architecture)**: The UI layers (Telegram bot and FastAPI routers) do not perform core logic or query database tables directly. They depend entirely on `StudyService` and `UserService`, which orchestrate repositories, extractor modules, and the LLM engine.
2. **Asynchronous Transactions**: SQLAlchemy `asyncio` is used with `aiosqlite` during development, and holds native compatibility with `asyncpg` for PostgreSQL production swapping.
3. **Structured Outputs**: Instead of using manual regex parsing to validate JSON answers from Gemini, we use the SDK's `generate_structured` method, supplying Pydantic schemas. This forces Gemini to output valid, structured JSON.
4. **Independent Microservices**: Scaling traffic can be handled by deploying multiple FastAPI backend containers behind a load balancer, while keeping the bot engine running as a single process (or transitioning to webhooks).
