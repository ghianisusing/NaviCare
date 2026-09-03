import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getConversation, sendMessage } from '../api/conversations'
import { confirmAgentAction, declineAgentAction } from '../api/appointments'
import { extractErrorMessage } from '../api/client'
import './chat.css'

const URGENCY_LABELS = {
  emergency: 'Urgent Medical Attention',
  urgent: 'Prompt Medical Attention Recommended',
}

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

function SlotOptions({ slots, onSelect, disabled }) {
  if (!slots || slots.length === 0) {
    return <p className="chat-appointment-empty">No available appointments matched that request.</p>
  }
  return (
    <div className="chat-slot-list">
      {slots.map((slot, index) => (
        <div key={index} className="chat-slot-card">
          <div>
            <div className="chat-slot-provider">{slot.provider_name}</div>
            <div className="chat-slot-department">{slot.department_name}</div>
            <div className="chat-slot-time">{formatDateTime(slot.start_time)}</div>
          </div>
          <button
            className="btn btn-secondary"
            disabled={disabled}
            onClick={() =>
              onSelect(
                `Book the appointment with ${slot.provider_name} on ${formatDateTime(slot.start_time)}.`
              )
            }
          >
            Select
          </button>
        </div>
      ))}
    </div>
  )
}

function AppointmentList({ appointments }) {
  if (!appointments || appointments.length === 0) {
    return <p className="chat-appointment-empty">No appointments found.</p>
  }
  return (
    <div className="chat-slot-list">
      {appointments.map((appointment) => (
        <div key={appointment.id} className="chat-slot-card">
          <div>
            <div className="chat-slot-provider">{appointment.provider_name}</div>
            <div className="chat-slot-department">{appointment.department_name}</div>
            <div className="chat-slot-time">
              {formatDateTime(appointment.start_time)} · {appointment.status}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function FollowUpList({ followUps }) {
  if (!followUps || followUps.length === 0) {
    return <p className="chat-appointment-empty">No follow-ups found.</p>
  }
  return (
    <div className="chat-slot-list">
      {followUps.map((followUp) => (
        <div key={followUp.id} className="chat-slot-card">
          <div>
            <div className="chat-slot-provider">{followUp.title}</div>
            <div className="chat-slot-time">
              {followUp.due_at ? `Due ${formatDateTime(followUp.due_at)} · ` : ''}
              {followUp.status}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ReminderList({ reminders }) {
  if (!reminders || reminders.length === 0) {
    return <p className="chat-appointment-empty">No reminders found.</p>
  }
  return (
    <div className="chat-slot-list">
      {reminders.map((reminder) => (
        <div key={reminder.id} className="chat-slot-card">
          <div>
            <div className="chat-slot-provider">{reminder.follow_up_title}</div>
            <div className="chat-slot-time">
              {formatDateTime(reminder.scheduled_for)} · {reminder.status}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function PendingActionCard({ pendingAction, onSelect, disabled }) {
  const [resolution, setResolution] = useState(null) // 'confirmed' | 'declined' | error string
  const [busy, setBusy] = useState(false)

  async function handleConfirm() {
    setBusy(true)
    try {
      await confirmAgentAction(pendingAction.id)
      setResolution('confirmed')
    } catch (err) {
      setResolution(extractErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleDecline() {
    setBusy(true)
    try {
      await declineAgentAction(pendingAction.id)
      setResolution('declined')
    } catch (err) {
      setResolution(extractErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (resolution === 'confirmed') {
    return <div className="chat-pending-resolved chat-pending-confirmed">✓ Done — {pendingAction.summary}</div>
  }
  if (resolution === 'declined') {
    return <div className="chat-pending-resolved">No problem — nothing was changed.</div>
  }

  return (
    <div className="chat-pending-card">
      <div className="chat-pending-summary">{pendingAction.summary}</div>
      {resolution && <div className="alert-error chat-pending-error">{resolution}</div>}
      <div className="chat-pending-actions">
        <button className="btn btn-primary" onClick={handleConfirm} disabled={busy || disabled}>
          Confirm
        </button>
        <button className="btn btn-secondary" onClick={handleDecline} disabled={busy || disabled}>
          Choose another
        </button>
      </div>
    </div>
  )
}

function MessageBubble({ message, onQuickMessage, sending }) {
  const urgency = message.urgency
  const isFlagged = urgency === 'emergency' || urgency === 'urgent'
  const appointmentData = message.appointment_data
  const followUpData = message.follow_up_data

  return (
    <div className={`chat-bubble-row ${message.role}`}>
      <div className={`chat-bubble ${message.role} ${isFlagged ? `chat-bubble-${urgency}` : ''}`}>
        {isFlagged && (
          <div className="chat-urgency-banner">
            <span aria-hidden="true">⚠️</span> {URGENCY_LABELS[urgency]}
          </div>
        )}
        <p className="chat-bubble-text">{message.content}</p>

        {message.sources && message.sources.length > 0 && (
          <div className="chat-sources">
            <div className="chat-sources-label">Sources</div>
            <ul>
              {message.sources.map((source, index) => (
                <li key={index}>
                  {source.source_url ? (
                    <a href={source.source_url} target="_blank" rel="noreferrer">
                      {source.title}
                    </a>
                  ) : (
                    <span>{source.title}</span>
                  )}
                  {source.source && <span className="chat-source-publisher"> — {source.source}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {appointmentData?.type === 'slot_options' && (
          <SlotOptions slots={appointmentData.slots} onSelect={onQuickMessage} disabled={sending} />
        )}
        {appointmentData?.type === 'appointment_list' && <AppointmentList appointments={appointmentData.appointments} />}

        {followUpData?.type === 'follow_up_list' && <FollowUpList followUps={followUpData.follow_ups} />}
        {followUpData?.type === 'reminder_list' && <ReminderList reminders={followUpData.reminders} />}

        {message.pending_action && <PendingActionCard pendingAction={message.pending_action} disabled={sending} />}
      </div>
    </div>
  )
}

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

  async function sendComposed(content) {
    if (!content || sending) return
    setMessages((prev) => [
      ...prev,
      { id: `pending-${Date.now()}`, role: 'user', content, created_at: new Date().toISOString() },
    ])
    await deliver(content)
  }

  async function handleSend(event) {
    event.preventDefault()
    const content = draft.trim()
    if (!content) return
    setDraft('')
    await sendComposed(content)
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
          <h1>NaviCare</h1>
          <p className="chat-status">
            <span className="status-dot" aria-hidden="true" />
            Online
          </p>
        </div>
      </div>

      <p className="chat-intro">
        Your Patient Navigator. I can help you understand general healthcare information, navigate
        healthcare services, find and book appointments, and figure out what kind of help you may need.
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
            <MessageBubble key={message.id} message={message} onQuickMessage={sendComposed} sending={sending} />
          ))}

        {sending && (
          <div className="chat-bubble-row assistant">
            <div className="chat-bubble assistant chat-typing" aria-label="NaviCare is typing">
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
