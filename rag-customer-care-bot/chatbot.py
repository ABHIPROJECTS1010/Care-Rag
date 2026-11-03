import logging
import os

import ollama
from vector_store import search

# --- Logging setup: metadata only — never log raw user messages (SEC-05) ---
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chatbot.log")
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

PROMPT_TEMPLATE = """You are a customer support assistant for Care-RAG.

STRICT RULES:
- Only use facts explicitly stated in the Context below.
- If the Context does not directly and specifically answer the Question, respond with EXACTLY: "I'm sorry, I don't have information on that. Would you like me to connect you to a human agent?"
- Do not guess, infer, or add any information not explicitly written in the Context, even if it seems reasonable.
- Keep the conversation history in mind for follow-up questions (e.g. "what about X" refers back to the previous topic).

Conversation so far:
{history}

Context:
{context}

Question: {question}

Answer:"""

GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hiya", "yo"}
ESCALATION_PHRASES = {"connect me to a human", "talk to an agent", "speak to a human", "human agent", "escalate"}


class ChatSession:
    def __init__(self):
        self.history = []  # list of (question, answer) tuples

    def _format_history(self) -> str:
        if not self.history:
            return "(no previous messages)"
        formatted = []
        for q, a in self.history[-3:]:  # keep last 3 exchanges for context
            formatted.append(f"Customer: {q}\nAssistant: {a}")
        return "\n\n".join(formatted)

    def reset(self):
        self.history = []
        logging.info("Session history reset.")

    def get_answer(self, question: str) -> str:
        normalized = question.strip().lower().rstrip("!?.")

        # --- 1. Handle greetings without running retrieval ---
        if any(normalized == g or normalized.startswith(g + " ") for g in GREETINGS):
            answer = "Hello! Welcome to Care-RAG support. How can I help you today?"
            logging.info("ROUTE: greeting")
            self.history.append((question, answer))
            return answer

        # --- 2. Handle escalation requests ---
        if any(phrase in normalized for phrase in ESCALATION_PHRASES):
            answer = ("I'll connect you to a human agent. Our live chat is available "
                      "Monday-Saturday, 8 AM - 10 PM. Outside those hours, you can submit "
                      "a ticket and expect a response within 24 hours.")
            logging.info("ROUTE: escalation")
            self.history.append((question, answer))
            return answer

        # --- 3. Normal RAG flow ---
        # For follow-ups, combine the last question with the current one for better retrieval
        if self.history:
            last_question = self.history[-1][0]
            search_query = f"{last_question} {question}"
        else:
            search_query = question

        try:
            relevant_chunks = search(search_query, top_k=3, distance_threshold=0.6)
        except Exception as e:
            logging.error(f"Search retrieval error: {e}")
            relevant_chunks = []

        if not relevant_chunks:
            answer = "I'm sorry, I don't have information on that. Would you like me to connect you to a human agent?"
            logging.info("ROUTE: no_match")
            self.history.append((question, answer))
            return answer

        context = "\n\n".join([doc for doc, dist in relevant_chunks])


        prompt = PROMPT_TEMPLATE.format(
            history=self._format_history(),
            context=context,
            question=search_query
        )

        try:
            response = ollama.chat(
                model="llama3.1",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response["message"]["content"]
        except Exception as e:
            logging.warning(f"Ollama generation error or offline: {e}")
            # Fallback directly using top retrieved context if Ollama is not running
            answer = f"Based on Care-RAG Help Center:\n\n{relevant_chunks[0][0]}"

        # Log only retrieval metadata — never the raw question or answer text
        top_dist = relevant_chunks[0][1] if relevant_chunks else -1.0
        logging.info(
            f"ROUTE: rag | CHUNKS: {len(relevant_chunks)} | TOP_DIST: {top_dist:.3f}"
        )
        self.history.append((question, answer))
        return answer


if __name__ == "__main__":
    session = ChatSession()

    test_conversation = [
        "Hi there!",
        "How do I track my order?",
        "What about if it's been more than 24 hours?",
        "connect me to a human",
    ]

    for q in test_conversation:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print('='*60)
        answer = session.get_answer(q)
        print(f"A: {answer}")