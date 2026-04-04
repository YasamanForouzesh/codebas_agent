from openai import OpenAI
import httpx
import os


# runs once at startup
def _connect() -> tuple[OpenAI, str]:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        httpx.get(ollama_url, timeout=3).raise_for_status()
        return OpenAI(base_url=f"{ollama_url}/v1", api_key="ollama"), os.getenv("OLLAMA_MODEL_NAME")
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")


# module-level — created once when FastAPI starts
client, model = _connect()

# in-memory session storage
sessions: dict[str, list] = {}


def chat(session_id: str, message: str) -> str:

    history = sessions.get(session_id, [])
    history.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=model,
        messages=history,
    )  # uses module-level client and model
    reply = response.choices[0].message.content

    history.append({"role": "assistant", "content": reply})
    sessions[session_id] = history

    return reply


def reset(session_id: str):
    sessions.pop(session_id, None)
