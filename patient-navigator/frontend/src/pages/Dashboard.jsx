import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMyProfile } from '../api/patients'
import { createConversation, listConversations } from '../api/conversations'
import { extractErrorMessage } from '../api/client'
import './dashboard.css'

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [profile, setProfile] = useState(null)
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [startingChat, setStartingChat] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [profileData, conversationData] = await Promise.all([getMyProfile(), listConversations()])
        if (!cancelled) {
          setProfile(profileData)
          setConversations(conversationData)
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
  }, [])

  async function handleStartChat() {
    setStartingChat(true)
    try {
      const conversation = await createConversation()
      navigate(`/chat/${conversation.id}`)
    } catch (err) {
      setError(extractErrorMessage(err))
      setStartingChat(false)
    }
  }

  const displayName = profile?.first_name || user?.username || 'there'

  return (
    <div className="dashboard">
      <h1>Welcome, {displayName}</h1>
      <p className="dashboard-subtitle">Here's where you go when you need help navigating your care.</p>

      {error && <div className="alert-error">{error}</div>}

      <div className="card start-chat-card">
        <div>
          <h2>Start a conversation</h2>
          <p>Ask about your healthcare journey or next steps.</p>
        </div>
        <button className="btn btn-primary" onClick={handleStartChat} disabled={startingChat}>
          {startingChat ? 'Starting…' : 'Start chat'}
        </button>
      </div>

      <section className="recent-section">
        <h2>Recent conversations</h2>
        {loading && <p className="dashboard-muted">Loading…</p>}
        {!loading && conversations.length === 0 && (
          <div className="card empty-state">
            <p>You haven't started a conversation yet.</p>
            <p className="dashboard-muted">Start one above whenever you have a question.</p>
          </div>
        )}
        {!loading && conversations.length > 0 && (
          <ul className="conversation-list">
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <button className="conversation-row" onClick={() => navigate(`/chat/${conversation.id}`)}>
                  <span className="conversation-title">{conversation.title || 'New conversation'}</span>
                  {conversation.last_message && (
                    <span className="conversation-preview">{conversation.last_message.content}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
