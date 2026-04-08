import json
import os

import httpx
from openai import OpenAI

from tools.gitlab import TOOL_DEFINITIONS, TOOL_HANDLERS


# runs once at startup
def _connect() -> tuple[OpenAI, str]:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        httpx.get(ollama_url, timeout=3).raise_for_status()
        return OpenAI(base_url=f"{ollama_url}/v1", api_key="ollama"), os.getenv("OLLAMA_MODEL", "qwen3:8b")
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")


# module-level — created once when FastAPI starts
client, model = _connect()

SYSTEM_PROMPT = (
    "You are a codebase assistant helping a backend engineer understand how code is used across repositories.\n\n"
    "Your job is to answer questions about code usage, API usage, operationId usage, and possible frontend/backend connections by using the available tools.\n\n"
    "Rules:\n"
    "Use the tools when the answer depends on repository contents. Do not guess.\n"
    "If the user’s question is ambiguous and you are not sure which project or repository to search, ask a short clarifying question.\n"
    "If multiple repositories may be relevant, say that clearly and ask whether to search one specific repository or all relevant repositories.\n"
    "Prefer exact identifiers when possible, especially:\n"
    "apiName.operationId\n"
    "operationId\n"
    "endpoint path\n"
    "function name\n"
    "file name\n"
    "When you find matches, explain the result clearly:\n"
    "repository name\n"
    "file path\n"
    "function or component name if visible\n"
    "short explanation of why it is relevant\n"
    "If you do not find enough evidence, say so clearly. Do not invent usage.\n"
    "Be concise, technical, and practical.\n"
    "If the user asks where something is used, first search code, then read the most relevant files before answering.\n"
    "If the user asks about UI usage, try to identify the likely page/component/file, but be explicit when something is an inference rather than a direct fact.\n"
    "If there are multiple matches, summarize the top relevant ones instead of dumping raw results.\n\n"
    "Tool usage policy:\n"
    "Use search_code to find references across repositories.\n"
    "Use read_file to inspect the most relevant files before answering.\n"
    "Ask the user for clarification if project selection is unclear and confidence is low.\n\n"
    "Response style:\n"
    "Be direct.\n"
    "Use short sections when helpful.\n"
    "Prefer exact evidence over broad explanations."
)

# in-memory session storage
sessions: dict[str, list] = {}


def chat(session_id: str, message: str) -> str:
    print(f"Session {session_id} sent message: {message}"  )
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    history = sessions[session_id]
    print(history)
    history.append({"role": "user", "content": message})

    while True:
        response = client.chat.completions.create(
            model=model,
            messages=history,
            tools=TOOL_DEFINITIONS,
            timeout=120,
        )

        message = response.choices[0].message
        history.append(message)

        if not message.tool_calls:
            break

        for tool_call in message.tool_calls:
            handler = TOOL_HANDLERS[tool_call.function.name]
            try:
                result = handler(json.loads(tool_call.function.arguments))
            except Exception as e:
                result = {"error": str(e)}
            print(f"Tool {tool_call.function.name} called with {tool_call.function.arguments} → {result}")
            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    reply = message.content
    sessions[session_id] = history

    return reply


def reset(session_id: str):
    sessions.pop(session_id, None)
