import ollama

response = ollama.chat(
    model="llama3.1",
    messages=[
        {"role": "user", "content": "Say hello and confirm you're ready to help build a RAG chatbot!"}
    ]
)

print(response["message"]["content"])