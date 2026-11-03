@echo off
echo Starting Care-RAG Support Backend API on http://127.0.0.1:8000 ...
echo.

if exist .venv\Scripts\python.exe (
    set "PYTHON_CMD=.\.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=py -3.11"
)

echo Using Python runtime: %PYTHON_CMD%
%PYTHON_CMD% -m uvicorn api:app --host 127.0.0.1 --port 8000
pause
