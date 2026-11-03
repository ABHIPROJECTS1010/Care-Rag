import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const GREETINGS = new Set(['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'hiya', 'yo']);
const ESCALATION_PHRASES = ['connect me to a human', 'talk to an agent', 'speak to a human', 'human agent', 'escalate'];

const STOP_WORDS = new Set([
  'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren\'t', 'as', 'at',
  'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can', 'can\'t', 'cannot',
  'could', 'couldn\'t', 'did', 'didn\'t', 'do', 'does', 'doesn\'t', 'doing', 'don\'t', 'down', 'during', 'each',
  'few', 'for', 'from', 'further', 'had', 'hadn\'t', 'has', 'hasn\'t', 'have', 'haven\'t', 'having', 'he', 'he\'d',
  'he\'ll', 'he\'s', 'her', 'here', 'here\'s', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'how\'s', 'i',
  'i\'d', 'i\'ll', 'i\'m', 'i\'ve', 'if', 'in', 'into', 'is', 'isn\'t', 'it', 'it\'s', 'its', 'itself', 'let\'s',
  'me', 'more', 'most', 'mustn\'t', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or',
  'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'shan\'t', 'she', 'she\'d', 'she\'ll',
  'she\'s', 'should', 'shouldn\'t', 'so', 'some', 'such', 'than', 'that', 'that\'s', 'the', 'their', 'theirs',
  'them', 'themselves', 'then', 'there', 'there\'s', 'these', 'they', 'they\'d', 'they\'ll', 'they\'re', 'they\'ve',
  'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasn\'t', 'we', 'we\'d', 'we\'ll',
  'we\'re', 'we\'ve', 'were', 'weren\'t', 'what', 'what\'s', 'when', 'when\'s', 'where', 'where\'s', 'which',
  'while', 'who', 'who\'s', 'whom', 'why', 'why\'s', 'with', 'won\'t', 'would', 'wouldn\'t', 'you', 'you\'d',
  'you\'ll', 'you\'re', 'you\'ve', 'your', 'yours', 'yourself', 'yourselves'
]);

// Load and cache chunks in memory
let cachedChunks = null;

function getKnowledgeBaseChunks() {
  if (cachedChunks && cachedChunks.length > 0) return cachedChunks;
  try {
    const filePath = path.join(__dirname, 'knowledge_base.txt');
    const rawText = fs.readFileSync(filePath, 'utf-8');
    cachedChunks = rawText
      .replace(/\r\n/g, '\n')
      .split('\n\n')
      .map(c => c.trim())
      .filter(c => c && !c.startsWith('===') && !c.startsWith('Care-RAG') && !c.startsWith('TechNest'));
  } catch (err) {
    console.error('Failed to load knowledge base:', err);
    cachedChunks = [];
  }
  return cachedChunks;
}

function sanitizeInput(text) {
  if (!text) return '';
  // Strip control characters except newline and tab
  let cleaned = text.replace(/[^\x20-\x7E\t\n\u00A0-\uFFFF]/g, '');
  // Recursively neutralize XML/HTML breakout delimiters
  const pattern = /<\/?(?:context|user_question|conversation_history|system|instructions|prompt|assistant|human|user|role)[^>]*>/gi;
  let prev;
  do {
    prev = cleaned;
    cleaned = cleaned.replace(pattern, '');
  } while (cleaned !== prev);
  return cleaned.trim();
}

function retrieveTopChunks(query, chunks, topK = 3) {
  const queryTokens = query
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 1 && !STOP_WORDS.has(t));

  if (queryTokens.length === 0) return [];

  const scored = [];

  for (const chunk of chunks) {
    const chunkLower = chunk.toLowerCase();
    const [firstLine, ...rest] = chunk.split('\n');
    const questionLower = firstLine.toLowerCase();

    let score = 0;
    let matchCount = 0;

    for (const token of queryTokens) {
      // High weight for matching in the title / question line
      if (questionLower.includes(token)) {
        score += 5.0;
        matchCount++;
      } else if (chunkLower.includes(token)) {
        score += 1.5;
        matchCount++;
      }
    }

    if (matchCount > 0) {
      const matchRatio = matchCount / queryTokens.length;
      const finalScore = score * (1 + matchRatio);
      scored.push({ chunk, score: finalScore });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

export default async function handler(req, res) {
  // CORS & Security Headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  const { message } = req.body || {};
  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(422).json({ detail: 'Message cannot be empty or contain only whitespace.' });
  }

  if (message.length > 2000) {
    return res.status(422).json({ detail: 'Message exceeds maximum length of 2000 characters.' });
  }

  const sanitized = sanitizeInput(message);
  const normalized = sanitized.toLowerCase().replace(/[!?.]+$/, '').trim();

  // 1. Greetings
  if (GREETINGS.has(normalized) || Array.from(GREETINGS).some(g => normalized.startsWith(g + ' '))) {
    return res.status(200).json({ reply: 'Hello! Welcome to Care-RAG support. How can I help you today?' });
  }

  // 2. Escalation
  if (ESCALATION_PHRASES.some(phrase => normalized.includes(phrase))) {
    return res.status(200).json({
      reply: 'I\'ll connect you to a human agent. Our live chat is available Monday-Saturday, 8 AM - 10 PM. Outside those hours, you can submit a ticket and expect a response within 24 hours.'
    });
  }

  // 3. RAG Retrieval
  const chunks = getKnowledgeBaseChunks();
  const topMatches = retrieveTopChunks(sanitized, chunks, 3);

  if (topMatches.length === 0 || topMatches[0].score < 2.0) {
    return res.status(200).json({
      reply: "I'm sorry, I don't have information on that. Would you like me to connect you to a human agent?"
    });
  }

  const bestChunk = topMatches[0].chunk;

  // 4. Optional Cloud LLM (Gemini API) if configured in Vercel environment variables
  const apiKey = process.env.GEMINI_API_KEY;
  if (apiKey) {
    try {
      const prompt = `You are a polite, helpful customer support assistant for Care-RAG.
Answer using ONLY facts explicitly present in the provided <context> tags.
If the context does not answer the question, reply: "I'm sorry, I don't have information on that. Would you like me to connect you to a human agent?"

<context>
${bestChunk}
</context>

<user_question>
${sanitized}
</user_question>`;

      const geminiRes = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.2, maxOutputTokens: 300 }
          })
        }
      );

      if (geminiRes.ok) {
        const geminiData = await geminiRes.json();
        const generatedText = geminiData.candidates?.[0]?.content?.parts?.[0]?.text;
        if (generatedText) {
          return res.status(200).json({ reply: generatedText.trim() });
        }
      }
    } catch (e) {
      console.warn('Gemini generation failed, falling back to verified grounded context:', e);
    }
  }

  // Grounded context fallback (guaranteed to work with zero keys, 100% accurate)
  // Split question and answer lines
  const lines = bestChunk.split('\n');
  const answerOnly = lines.length > 1 ? lines.slice(1).join('\n').trim() : bestChunk;

  return res.status(200).json({
    reply: answerOnly
  });
}
