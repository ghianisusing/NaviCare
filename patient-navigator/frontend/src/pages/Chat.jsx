import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getConversation, sendMessage } from '../api/conversations'
import { extractErrorMessage } from '../api/client'
import './chat.css'

export default function Chat() {
  const { conversationId } = useParams()
  const navigate = useNavigate()

  const [conversation, setConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [failedMessage, setFailedMessage] = useState(null)

  const bottomRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getConversation(conversationId)
        if (!cancelled) {
          setConversation(data)
          setMessages(data.messages || [])
        }
      } catch (err) {
        if (!cancelled) setError(extractErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function deliver(content) {
    setSending(true)
    setError('')
    setFailedMessage(null)

    try {
      const reply = await sendMessage(conversationId, content)
      setMessages((prev) => [...prev, reply])
    } catch (err) {
      setError(extractErrorMessage(err))
      setFailedMessage(content)
    } finally {
      setSending(false)
    }
  }

  async function handleSend(event) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || sending) return

    // Optimistic add of the patient's own message; the assistant reply
    // is appended once the server responds.
    setMessages((prev) => [
      ...prev,
      { id: `pending-${Date.now()}`, role: 'user', content, created_at: new Date().toISOString() },
    ])
    setDraft('')
    await deliver(content)
  }

  async function handleRetry() {
    if (!failedMessage) return
    await deliver(failedMessage)
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <button className="chat-back" onClick={() => navigate('/dashboard')} aria-label="Back to dashboard">
          ←
        </button>
        <div>
          <h1>Patient Navigator</h1>
          <p className="chat-status">
            <span className="status-dot" aria-hidden="true" />
            Online
          </p>
        </div>
      </div>

      <p className="chat-intro">
        I'm here to help you navigate your healthcare needs and figure out what to do next.
      </p>

      {error && (
        <div className="alert-error chat-error">
          <span>{error}</span>
          {failedMessage && (
            <button type="button" className="chat-retry-link" onClick={handleRetry} disabled={sending}>
              Retry
            </button>
          )}
        </div>
      )}

      <div className="chat-window card">
        {loading && <p className="dashboard-muted chat-loading">Loading conversation…</p>}

        {!loading && messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask about your healthcare journey or next steps.</p>
          </div>
        )}

        {!loading &&
          messages.map((message) => (
            <div key={message.id} className={`chat-bubble-row ${message.role}`}>
              <div className={`chat-bubble ${message.role}`}>{message.content}</div>
            </div>
          ))}

        {sending && (
          <div className="chat-bubble-row assistant">
            <div className="chat-bubble assistant chat-typing" aria-label="Patient Navigator is typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="chat-composer" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="Type a message…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={loading || sending}
        />
        <button className="btn btn-primary" type="submit" disabled={loading || sending || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
