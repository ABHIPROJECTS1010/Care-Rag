export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.status(200).json({
    status: 'online',
    service: 'Care-RAG Support Chatbot API (Vercel Serverless)',
    version: '1.0.0'
  });
}

