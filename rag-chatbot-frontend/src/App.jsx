import { useState, useRef, useEffect } from 'react'
import SearchModal from './components/SearchModal'
import ConfirmModal from './components/ConfirmModal'
import PlasmaWave from './components/PlasmaWave/PlasmaWave'
import './App.css'

function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  )
}

const STARTER_PROMPTS = [
  { icon: '📦', text: 'How do I track my order?' },
  { icon: '🔄', text: 'What is your return policy?' },
  { icon: '🛡️', text: 'How do I claim a warranty repair?' },
  { icon: '🎧', text: 'How do I speak to a human agent?' },
]

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (typeof window !== 'undefined' && window.location.port === '8000' ? '' : 'http://localhost:8000')

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [confirmModalOpen, setConfirmModalOpen] = useState(false)
  const chatEndRef = useRef(null)
  const textareaRef = useRef(null)

  const isChatActive = messages.length > 0

  useEffect(() => {
    if (isChatActive) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading, isChatActive])

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`
    }
  }

  const sendMessage = async (overrideText) => {
    const text = (overrideText ?? input).trim()
    if (!text || loading) return

    const userMessage = { role: 'user', content: text }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setLoading(true)

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          message: text
        })
      })
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`)
      }
      const data = await response.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ Unable to connect. Please try again in a moment or contact support.'
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleSelectQuestion = (question) => {
    sendMessage(question)
  }

  const handleNewChatClick = () => {
    if (messages.length > 0) {
      setConfirmModalOpen(true)
    } else {
      handleConfirmNewChat()
    }
  }

  const handleConfirmNewChat = async () => {
    setConfirmModalOpen(false)
    setMessages([])
    setInput('')
    try {
      await fetch(`${API_BASE_URL}/reset`, {
        method: 'POST',
        credentials: 'include'
      })
    } catch {
      // Silently ignore if offline
    }
  }

  return (
    <div className={`app-container ${isChatActive ? 'chat-mode-active' : 'initial-mode'}`}>
      {/* Background PlasmaWave animation - stays strictly in background */}
      <div className="plasma-background">
        <PlasmaWave
          colors={["#A855F7", "#06B6D4"]}
          speed1={0.05}
          speed2={0.05}
          focalLength={0.8}
          bend1={1}
          bend2={0.5}
          dir2={1.0}
          rotationDeg={0}
        />
      </div>

      {/* Top Navbar */}
      <header className={`top-navbar ${isChatActive ? 'compact' : ''}`}>
        <div className="nav-brand">
          <span className="brand-logo">🛠️</span>
          <span className="brand-name">Care-RAG</span>
        </div>
        {isChatActive && (
          <button className="new-chat-btn" onClick={handleNewChatClick} title="Start new chat">
            <span>+</span> New Chat
          </button>
        )}
      </header>

      {/* Main Container */}
      <div className={`main-content-layout ${isChatActive ? 'in-chat' : 'in-hero'}`}>
        {!isChatActive ? (
          /* Initial State: Gemini-style Centered Layout */
          <div className="gemini-hero-center">
            <div className="hero-badge">Care-RAG AI</div>
            <h1 className="hero-greeting">
              How can I help you today?
            </h1>
            <p className="hero-subtext">
              Ask about orders, warranties, troubleshooting, or product support
            </p>

            {/* Centered Search Bar */}
            <div className="search-bar-outer centered">
              <div className="search-bar-card">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  maxLength={2000}
                  onChange={(e) => {
                    setInput(e.target.value)
                    adjustTextareaHeight()
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Care-RAG Assistant..."
                  disabled={loading}
                  className="search-textarea"
                />

                <div className="search-bar-bottom">
                  <div className="pill-group">
                    <button
                      type="button"
                      className="pill-btn topics-pill"
                      onClick={() => setModalOpen(true)}
                      title="Browse Help Topics"
                    >
                      <span>✨ Topics</span>
                    </button>
                  </div>

                  <div className="action-group">
                    <button
                      type="button"
                      className={`send-circle-btn ${(input.trim() && !loading) ? 'active' : ''}`}
                      onClick={() => sendMessage()}
                      disabled={!input.trim() || loading}
                      title="Send message"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="12" y1="19" x2="12" y2="5" />
                        <polyline points="5 12 12 5 19 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Starters under centered search bar */}
            <div className="starter-chips">
              {STARTER_PROMPTS.map((prompt, idx) => (
                <button
                  key={idx}
                  className="starter-chip"
                  onClick={() => sendMessage(prompt.text)}
                >
                  <span className="starter-chip-icon">{prompt.icon}</span>
                  <span className="starter-chip-text">{prompt.text}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Active Chat State: Messages flow with Search bar at bottom */
          <div className="chat-flow-container">
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  {msg.role === 'assistant' && <div className="ai-avatar">🛠️</div>}
                  <div className="message-bubble">{msg.content}</div>
                </div>
              ))}
              {loading && (
                <div className="message assistant">
                  <div className="ai-avatar">🛠️</div>
                  <div className="message-bubble typing-bubble">
                    <TypingIndicator />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Bottom-anchored Search Bar in active chat mode */}
            <div className="search-bar-outer bottom-anchored">
              <div className="search-bar-card">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  maxLength={2000}
                  onChange={(e) => {
                    setInput(e.target.value)
                    adjustTextareaHeight()
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder="Message Care-RAG Assistant..."
                  disabled={loading}
                  className="search-textarea"
                />

                <div className="search-bar-bottom">
                  <div className="pill-group">
                    <button
                      type="button"
                      className="pill-btn topics-pill"
                      onClick={() => setModalOpen(true)}
                      title="Browse Help Topics"
                    >
                      <span>✨ Topics</span>
                    </button>
                  </div>

                  <div className="action-group">
                    <button
                      type="button"
                      className={`send-circle-btn ${(input.trim() && !loading) ? 'active' : ''}`}
                      onClick={() => sendMessage()}
                      disabled={!input.trim() || loading}
                      title="Send message"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="12" y1="19" x2="12" y2="5" />
                        <polyline points="5 12 12 5 19 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <SearchModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSelectQuestion={handleSelectQuestion}
      />

      <ConfirmModal
        isOpen={confirmModalOpen}
        title="Start a new conversation?"
        message="Starting a new chat will reset your current conversation. Would you like to start fresh or keep your current chat?"
        confirmText="Start New Chat"
        cancelText="Keep Current Chat"
        onConfirm={handleConfirmNewChat}
        onCancel={() => setConfirmModalOpen(false)}
      />
    </div>
  )
}

export default App