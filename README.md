# 🤖 Codebase Agent

An AI-powered codebase agent that supports multiple LLM providers with automatic fallback, served as a FastAPI web API.

---

## 📁 Project Structure

```
codebase-agent/
├── main.py              # FastAPI app — routes and entry point
├── llm_client.py        # LLM client with Ollama → OpenAI fallback and session history
├── gitlab_client.py     # GitLab API client
├── templates/
│   └── index.html       # Chat UI for testing endpoints
├── pyproject.toml       # Project dependencies
└── .env                 # Environment variables (not committed)
```

---

## ⚙️ Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- [Ollama](https://ollama.com) installed locally (optional)

### Install dependencies

```bash
uv sync
```

### Configure environment variables

Create a `.env` file in the project root:

```env
# Ollama (optional — falls back to OpenAI if not running)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL_NAME=llama3

# OpenAI (used as fallback if Ollama is not running)
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL_NAME=gpt-4o-mini
```

---

## 🏗️ Architecture

### LLM Client with Automatic Fallback

`llm_client.py` uses the OpenAI client for both providers — Ollama exposes an OpenAI-compatible API via `base_url`.

On startup it pings Ollama. If running, it uses Ollama. If not, it falls back to OpenAI automatically:

```python
# runs once at module import (FastAPI startup)
client, model = _connect()
```

No separate packages needed for Ollama — just the `openai` package pointed at a different URL.

### Conversation History

History is stored in-memory per session using a `session_id` as the key:

```python
sessions: dict[str, list] = {}
```

Each `chat()` call loads the history, appends the new message, sends the full context to the LLM, and saves it back. This gives the LLM memory of the full conversation.

### FastAPI Lifecycle

Module-level code in `llm_client.py` runs once when FastAPI imports the file at startup:
- `_connect()` — pings Ollama, picks provider
- `client, model` — created once, reused for every request
- `sessions` — in-memory store, lives for the lifetime of the server

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Chat UI (browser) |
| `POST` | `/chat` | Send a message |
| `POST` | `/reset` | Clear session history |

### POST /chat

```json
{
    "session_id": "user-123",
    "message": "Hello!"
}
```

Response:
```json
{
    "reply": "Hi! How can I help you?"
}
```

### POST /reset

```
/reset?session_id=user-123
```

---

## 📦 Dependencies

| Package         | Purpose                                      |
|-----------------|----------------------------------------------|
| `fastapi`       | Web framework                                |
| `uvicorn`       | ASGI server to run FastAPI                   |
| `openai`        | LLM client (used for both OpenAI and Ollama) |
| `python-dotenv` | Load environment variables                   |
| `httpx`         | HTTP client for Ollama health check          |

---

## 🚀 Run

```bash
uv run uvicorn main:app --reload
```

Then open `http://localhost:8000` for the chat UI or `http://localhost:8000/docs` for the interactive API docs.
