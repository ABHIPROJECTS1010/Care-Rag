import { useEffect } from 'react'

function ConfirmModal({ isOpen, title, message, confirmText = 'Start New Chat', cancelText = 'Keep Current Chat', onConfirm, onCancel }) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return
      if (e.key === 'Escape') {
        onCancel()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onCancel])

  if (!isOpen) return null

  return (
    <div className="modal-overlay confirm-modal-overlay" onClick={onCancel}>
      <div className="confirm-modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-icon-wrapper">
          <span className="confirm-icon">💬</span>
        </div>

        <h3 className="confirm-title">{title || 'Start a new conversation?'}</h3>
        
        <p className="confirm-message">
          {message || 'Starting a new chat will clear your active conversation history. Would you like to start fresh or keep chatting here?'}
        </p>

        <div className="confirm-actions">
          <button
            type="button"
            className="confirm-btn secondary-btn"
            onClick={onCancel}
          >
            {cancelText}
          </button>
          
          <button
            type="button"
            className="confirm-btn primary-btn"
            onClick={onConfirm}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfirmModal
