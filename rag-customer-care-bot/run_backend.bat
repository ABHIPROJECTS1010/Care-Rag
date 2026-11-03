@echo off
echo Starting Care-RAG Support Backend API on http://127.0.0.1:8000 ...
echo.
echo NOTE: Run with --reload flag only during development:
echo   .\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
echo.
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
pause
