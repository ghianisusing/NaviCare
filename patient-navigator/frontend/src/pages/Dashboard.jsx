import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMyProfile } from '../api/patients'
import { createConversation, listConversations } from '../api/conversations'
import { cancelAppointment, listAppointments } from '../api/appointments'
import { createAppointmentReminder } from '../api/followUps'
import { extractErrorMessage } from '../api/client'
import './dashboard.css'

function formatDateTime(isoString) {
  const date = new Date(isoString)
  return date.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [profile, setProfile] = useState(null)
  const [conversations, setConversations] = useState([])
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [startingChat, setStartingChat] = useState(false)
  const [cancellingId, setCancellingId] = useState(null)
  const [reminderState, setReminderState] = useState({}) // appointmentId -> 'busy' | 'done'

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [profileData, conversationData, appointmentData] = await Promise.all([
          getMyProfile(),
          listConversations(),
          listAppointments('scheduled'),
        ])
        if (!cancelled) {
          setProfile(profileData)
          setConversations(conversationData)
          setAppointments(appointmentData)
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

  async function handleCancelAppointment(id) {
    if (!window.confirm('Cancel this appointment?')) return
    setCancellingId(id)
    try {
      await cancelAppointment(id)
      setAppointments((prev) => prev.filter((a) => a.id !== id))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setCancellingId(null)
    }
  }

  async function handleRemindMe(id) {
    setReminderState((prev) => ({ ...prev, [id]: 'busy' }))
    try {
      await createAppointmentReminder(id)
      setReminderState((prev) => ({ ...prev, [id]: 'done' }))
    } catch (err) {
      setError(extractErrorMessage(err))
      setReminderState((prev) => ({ ...prev, [id]: undefined }))
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
        <h2>Upcoming appointments</h2>
        {loading && <p className="dashboard-muted">Loading…</p>}
        {!loading && appointments.length === 0 && (
          <div className="card empty-state">
            <p>No upcoming appointments.</p>
            <p className="dashboard-muted">Ask NaviCare to help you find and book one.</p>
          </div>
        )}
        {!loading && appointments.length > 0 && (
          <ul className="appointment-list">
            {appointments.map((appointment) => (
              <li key={appointment.id} className="card appointment-card">
                <div>
                  <div className="appointment-department">{appointment.department_name}</div>
                  <div className="appointment-provider">{appointment.provider_name}</div>
                  <div className="appointment-time">{formatDateTime(appointment.start_time)}</div>
                </div>
                <div className="appointment-actions">
                  {reminderState[appointment.id] === 'done' ? (
                    <span className="appointment-reminder-set">✓ Reminder set</span>
                  ) : (
                    <button
                      className="btn btn-secondary"
                      onClick={() => handleRemindMe(appointment.id)}
                      disabled={reminderState[appointment.id] === 'busy'}
                    >
                      {reminderState[appointment.id] === 'busy' ? 'Setting…' : 'Remind me'}
                    </button>
                  )}
                  <button className="btn btn-secondary" onClick={handleStartChat}>
                    Reschedule
                  </button>
                  <button
                    className="btn btn-secondary appointment-cancel-btn"
                    onClick={() => handleCancelAppointment(appointment.id)}
                    disabled={cancellingId === appointment.id}
                  >
                    {cancellingId === appointment.id ? 'Cancelling…' : 'Cancel'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

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
