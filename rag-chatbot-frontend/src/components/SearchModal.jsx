import { useState, useEffect } from 'react'
import { topics } from '../data/topics'

function SearchModal({ isOpen, onClose, onSelectQuestion }) {
  const [selectedTopic, setSelectedTopic] = useState(null)

  useEffect(() => {
    if (!isOpen) {
      const timer = setTimeout(() => setSelectedTopic(null), 200)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleTopicClick = (topic) => {
    setSelectedTopic(topic)
  }

  const handleBack = () => {
    setSelectedTopic(null)
  }

  const handleQuestionClick = (question) => {
    onSelectQuestion(question)
    onClose()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          {selectedTopic ? (
            <button className="modal-back" onClick={handleBack}>
              ← {selectedTopic.label}
            </button>
          ) : (
            <span className="modal-title">What do you need help with?</span>
          )}
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {!selectedTopic ? (
          <div className="topic-grid" key="level1">
            {topics.map((topic) => (
              <button
                key={topic.id}
                className="topic-chip"
                onClick={() => handleTopicClick(topic)}
              >
                <span className="topic-icon">{topic.icon}</span>
                <span>{topic.label}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="question-list" key="level2">
            {selectedTopic.questions.map((q, i) => (
              <button
                key={i}
                className="question-item"
                onClick={() => handleQuestionClick(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SearchModal