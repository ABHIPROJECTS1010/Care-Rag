import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from chatbot import ChatSession

app = FastAPI(title="Care-RAG Support Chatbot API")

# --- Allow React frontend (and any local dev port) to call this API ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Shared chat session ---
session = ChatSession()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "Care-RAG Support Chatbot API",
        "version": "1.0.0"
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer = session.get_answer(request.message)
    return ChatResponse(reply=answer)


@app.post("/reset")
def reset():
    session.reset()
    return {"status": "success", "message": "Chat history cleared"}


# --- Serve built frontend for a single unified URL ---
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag-chatbot-frontend", "dist"))

if os.path.exists(FRONTEND_DIST):
    assets_path = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str = ""):
        target_file = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.exists(target_file) and os.path.isfile(target_file):
            return FileResponse(target_file)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
