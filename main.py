from dotenv import load_dotenv
load_dotenv()  # must be first before any other imports that use env vars

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from llm_client import chat, reset


app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index():
    return open("templates/index.html").read()

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    reply = chat(request.session_id, request.message)
    return {"reply": reply}


@app.post("/reset")
def reset_endpoint(session_id: str):
    reset(session_id)
    return {"status": "session cleared"}

