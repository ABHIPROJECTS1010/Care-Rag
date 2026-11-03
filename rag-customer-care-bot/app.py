import streamlit as st
from chatbot import ChatSession

st.set_page_config(page_title="Care-RAG Support Chat", page_icon="🛠️")

st.title("🛠️ Care-RAG — Customer Support")
st.caption("Ask me about orders, returns, warranty, payments, or account help.")

# --- Initialize chat session (persists across reruns using Streamlit's session_state) ---
if "chat_session" not in st.session_state:
    st.session_state.chat_session = ChatSession()

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Display past messages ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- Chat input ---
user_input = st.chat_input("Type your question here...")

if user_input:
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Get bot response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = st.session_state.chat_session.get_answer(user_input)
        st.write(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})