# 🤖 Codebase Agent

An AI-powered codebase investigation agent that searches GitLab repositories to answer questions about code usage, API endpoints, and cross-repo connections. Supports multiple LLM providers with automatic fallback.

---

## 📁 Project Structure

```
codebase-agent/
├── main.py                          # Entry point — Gradio UI
├── llm_client.py                    # LLM client, session history, system prompt
├── gitlab_client.py                 # Standalone GitLab client (proxy)
├── git.py                           # GitLab client wrapper
├── tools/
│   └── gitlab.py                    # GitLab tool definitions, handlers, scoring
├── config/
│   ├── project_definitions.json     # Known projects with IDs, descriptions, keywords
│   └── project_definition_example.json
├── pyproject.toml                   # Project dependencies
└── .env                             # Environment variables (not committed)
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
# LLM — Ollama (optional, falls back to OpenAI if not running)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# LLM — OpenAI fallback
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL_NAME=gpt-4o-mini

# GitLab — proxy (BE/FE)
GITLAB_PROXY_URL=https://your-gitlab.com
GITLAB_PROXY_TOKEN=your_proxy_token

# GitLab — client side
GITLAB_CLIENT_URL=https://your-client-gitlab.com
GITLAB_CLIENT_TOKEN=your_client_token

# Project definitions
PROJECT_DEFINITIONS_FILE=config/project_definitions.json
```

---

## 🏗️ Architecture

### LLM Client with Automatic Fallback

On startup `llm_client.py` pings Ollama. If running, it uses Ollama. If not, falls back to OpenAI automatically. Both use the `openai` package — Ollama exposes an OpenAI-compatible API via `base_url`.

```
startup → ping Ollama → running? use Ollama : use OpenAI
```

### Agent Tool Loop

The agent runs in a loop — it calls tools until it has enough evidence to answer:

```
user message
    → LLM decides which tool to call
    → tool executes, result appended to history
    → LLM calls more tools or answers
    → reply returned
```

### Project Discovery

Known projects are loaded from `config/project_definitions.json` at startup. For ambiguous queries the agent calls `lookup_project`, which scores projects by name, description, and keyword overlap. If the project isn't in the list at all, it falls back to `list_projects`.

For ambiguous queries, `lookup_project` scores projects by name, description, and keyword overlap using token normalization (handles camelCase, snake_case, kebab-case).

### Search Result Ranking

`search_code` results are automatically ranked by `score_match` before being returned to the LLM:

- **+60** exact query match in snippet
- **+15** source file type (`.ts`, `.go`, `.py`, etc.)
- **+15** real code usage patterns (`useQuery`, `api.`, `fetch(`)
- **-15** noisy paths (`test`, `spec`, `mock`, `dist`)
- Boosted by `question_type`: `ui_usage` boosts frontend files, `endpoint_definition` boosts backend files

### Two GitLab Instances

The agent supports two GitLab sources configured separately:
- `proxy` — BE/FE repositories
- `client` — client-side repositories

The LLM passes `source` to every tool call to route to the correct instance.

### Conversation History

History is stored in-memory per session. The system prompt is injected once at session start.

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `lookup_project` | Score and rank projects by query — use when project is ambiguous |
| `get_project` | Fetch a project by numeric ID |
| `list_projects` | List all accessible projects, optionally filtered by group |
| `search_code` | Search code in a project — results auto-ranked by relevance |
| `read_file` | Read a file from a repository |
| `list_repository_tree` | List files and directories in a repo |
| `list_merge_requests` | List open MRs for a project |
| `search_merge_requests` | Search MRs by title |
| `get_merge_request` | Fetch an MR with full diffs |

---

## 📦 Dependencies

| Package         | Purpose                                      |
|-----------------|----------------------------------------------|
| `gradio`        | Chat UI                                      |
| `openai`        | LLM client (used for both OpenAI and Ollama) |
| `python-gitlab` | GitLab API client                            |
| `python-dotenv` | Load environment variables                   |
| `httpx`         | HTTP client for Ollama health check          |

---

## 🚀 Run

```bash
uv run python main.py
```

Then open `http://localhost:7860` in your browser.
