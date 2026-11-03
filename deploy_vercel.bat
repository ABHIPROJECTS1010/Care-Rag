@echo off
title Deploy Care-RAG to Vercel
echo ========================================================
echo  Deploying Care-RAG Support Chatbot to Vercel
echo ========================================================
echo.
cd /d "%~dp0\rag-chatbot-frontend"
echo Starting Vercel CLI deployment...
echo (If prompted, log in with your GitHub or Vercel account in the browser)
echo.
npx vercel
echo.
echo Deployment finished!
pause

