# Care-Rag

A retrieval-augmented generation (RAG) customer care chatbot designed to deliver verified, accurate customer support responses from a structured knowledge base.

## Problem it solves

Customer service teams often face slow response times and high volumes of repetitive inquiries regarding orders, returns, warranties, and account issues. Traditional keyword searches frequently fail to capture conversational queries, while ungrounded LLMs risk generating inaccurate answers. Care-Rag combines semantic vector search over a verified knowledge base with defensive prompt framing to deliver grounded, accurate answers without hallucinations.

## Features

- Grounded FAQ retrieval matching queries against domain-specific Q&A blocks
- Multi-client session isolation with HttpOnly cookies and LRU memory capacity controls
- Defense against prompt injection and XML delimiter breakout attacks
- Strict path traversal prevention ensuring static requests never leak files outside intended directories
- Per-IP rate limiting on chat and session reset endpoints via slowapi
- Automated human escalation routing for complex inquiries and live agent support
- Interactive React 19 UI featuring starter prompts, help topics modal, and background animations
- Serverless deployment compatibility on Vercel with optional Google Gemini API acceleration

## Tech stack

- Backend: FastAPI, Starlette, slowapi, Pydantic, Uvicorn, Streamlit
- Frontend: React 19, Vite, Three.js, React Three Fiber, OGL
- LLM and embeddings: Ollama (llama3.1), Google Gemini API (gemini-2.5-flash), all-MiniLM-L6-v2 (via ONNX runtime and Sentence Transformers)
- Vector store: ChromaDB (persistent local SQLite vector collection)
- Deployment: Vercel (serverless functions and static hosting), local batch scripts

## Installation and setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ABHIPROJECTS1010/Care-Rag.git
   cd Care-Rag
   ```

2. Set up the backend environment and install dependencies:
   ```bash
   cd rag-customer-care-bot
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   cd ..
   ```

3. Set up the frontend dependencies:
   ```bash
   cd rag-chatbot-frontend
   npm install
   cd ..
   ```

4. Create the `.env` file:
   Copy `.env.example` to `.env` in the project root or relevant subfolders:
   ```bash
   cp .env.example .env
   ```

5. Required environment variables:
   - `CORS_ALLOWED_ORIGINS`
   - `SESSION_TTL_SECONDS`
   - `MAX_SESSIONS`
   - `COOKIE_SECURE`
   - `ENVIRONMENT`
   - `VITE_API_BASE_URL`
   - `GEMINI_API_KEY`

## Usage

Start the backend API server:
```bash
cd rag-customer-care-bot
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
*(Alternatively, execute `rag-customer-care-bot\run_backend.bat`)*

Start the frontend development server:
```bash
cd rag-chatbot-frontend
npm run dev
```
*(Alternatively, execute `rag-chatbot-frontend\run_frontend.bat`)*

Example inquiry:
- User Question: "How do I track my order?"
- Bot Answer: "Once your order ships, you will receive an email with a tracking number and a link to the courier's tracking page. You can also log into your Care-RAG account, go to \"My Orders,\" and click \"Track Package\" next to the relevant order. Tracking information typically updates within 24 hours of dispatch."

## Screenshots / Demo

<video src="assets/demo.mp4" controls="controls" width="100%">
  Your browser does not support the video tag.
</video>

[Watch Demo Video (assets/demo.mp4)](assets/demo.mp4)

