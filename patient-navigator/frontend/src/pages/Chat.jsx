import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getConversation, sendMessage } from '../api/conversations'
import { confirmAgentAction, declineAgentAction } from '../api/appointments'
import { extractErrorMessage } from '../api/client'
import './chat.css'

const URGENCY_LABELS = {
  emergency: 'Immediate Emergency Care Needed',
  urgent: 'Prompt Clinical Attention Recommended',
}

const QUICK_STARTERS = [
  {
    icon: '📅',
    title: 'Schedule an Appointment',
    prompt: 'Help me find and schedule an appointment with an available doctor this week.',
  },
  {
    icon: '🩸',
    title: 'Lab & Test Preparation',
    prompt: 'What instructions should I follow before having routine fasting blood work done?',
  },
  {
    icon: '📋',
    title: 'Review My Follow-ups',
    prompt: 'Can you check my pending care tasks and tell me what follow-ups I need to complete?',
  },
  {
    icon: '🩺',
    title: 'Specialist Recommendation',
    prompt: 'I have persistent lower back pain. What kind of specialist or clinic should I see?',
  },
]

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
    return <p className="chat-appointment-empty">No available appointment slots matched that criteria.</p>
  }
  return (
    <div className="chat-slot-list">
      <div className="chat-slot-header">
        <span aria-hidden="true">🩺</span> Available Clinical Openings
      </div>
      {slots.map((slot, index) => (
        <div key={index} className="chat-slot-card">
          <div className="slot-info">
            <div className="chat-slot-department">{slot.department_name}</div>
            <div className="chat-slot-provider">{slot.provider_name}</div>
            <div className="chat-slot-time">
              <span aria-hidden="true">🗓️</span> {formatDateTime(slot.start_time)}
            </div>
          </div>
          <button
            className="btn btn-primary btn-sm chat-slot-select-btn"
            disabled={disabled}
            onClick={() =>
              onSelect(
                `Book the appointment with ${slot.provider_name} on ${formatDateTime(slot.start_time)}.`
              )
            }
          >
            Select Slot
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
          <div className="slot-info">
            <div className="chat-slot-department">{appointment.department_name}</div>
            <div className="chat-slot-provider">{appointment.provider_name}</div>
            <div className="chat-slot-time">
              {formatDateTime(appointment.start_time)} · <span className="badge badge-success">{appointment.status}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function FollowUpList({ followUps }) {
  if (!followUps || followUps.length === 0) {
    return <p className="chat-appointment-empty">No follow-ups recorded.</p>
  }
  return (
    <div className="chat-slot-list">
      {followUps.map((followUp) => (
        <div key={followUp.id} className="chat-slot-card">
          <div className="slot-info">
            <div className="chat-slot-provider">{followUp.title}</div>
            <div className="chat-slot-time">
              {followUp.due_at ? `Due: ${formatDateTime(followUp.due_at)} · ` : ''}
              <span className="badge badge-warning">{followUp.status}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ReminderList({ reminders }) {
  if (!reminders || reminders.length === 0) {
    return <p className="chat-appointment-empty">No active reminders found.</p>
  }
  return (
    <div className="chat-slot-list">
      {reminders.map((reminder) => (
        <div key={reminder.id} className="chat-slot-card">
          <div className="slot-info">
            <div className="chat-slot-provider">{reminder.follow_up_title}</div>
            <div className="chat-slot-time">
              Scheduled: {formatDateTime(reminder.scheduled_for)} · {reminder.status}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function PendingActionCard({ pendingAction, disabled }) {
  const [resolution, setResolution] = useState(null)
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
    return (
      <div className="chat-pending-resolved chat-pending-confirmed">
        <span aria-hidden="true">✓</span> Confirmed: {pendingAction.summary}
      </div>
    )
  }
  if (resolution === 'declined') {
    return (
      <div className="chat-pending-resolved">
        Selection cancelled — no changes were made to your schedule.
      </div>
    )
  }

  return (
    <div className="chat-pending-card">
      <div className="chat-pending-header">
        <span aria-hidden="true">📋</span> Action Confirmation
      </div>
      <div className="chat-pending-summary">{pendingAction.summary}</div>
      {resolution && <div className="alert-error chat-pending-error">{resolution}</div>}
      <div className="chat-pending-actions">
        <button className="btn btn-primary btn-sm" onClick={handleConfirm} disabled={busy || disabled}>
          {busy ? 'Confirming…' : 'Confirm Action'}
        </button>
        <button className="btn btn-secondary btn-sm" onClick={handleDecline} disabled={busy || disabled}>
          Choose Another
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
        {message.role === 'staff' && (
          <div className="chat-staff-banner">
            <span aria-hidden="true">👤</span> Care Support Coordinator (Staff)
          </div>
        )}
        {message.role === 'assistant' && (
          <div className="chat-role-indicator">
            <span aria-hidden="true">🩺</span> NaviCare Navigator
          </div>
        )}
        {isFlagged && (
          <div className="chat-urgency-banner">
            <span aria-hidden="true">⚠️</span> {URGENCY_LABELS[urgency]}
          </div>
        )}

        <p className="chat-bubble-text">{message.content}</p>

        {message.deliveryState === 'failed' && (
          <span className="chat-delivery-status" role="status">Not sent. Use “Retry Message” above to try again.</span>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="chat-sources">
            <div className="chat-sources-label">
              <span aria-hidden="true">🛡️</span> Verified Clinical Sources
            </div>
            <ul className="chat-sources-list">
              {message.sources.map((source, index) => (
                <li key={index} className="chat-source-item">
                  {source.source_url ? (
                    <a href={source.source_url} target="_blank" rel="noreferrer" className="source-title">
                      {source.title}
                    </a>
                  ) : (
                    <span className="source-title">{source.title}</span>
                  )}
                  {source.source && <span className="chat-source-publisher">({source.source})</span>}
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
  const location = useLocation()

  const [conversation, setConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [failedMessage, setFailedMessage] = useState(null)

  const bottomRef = useRef(null)
  const prefillHandled = useRef(false)
  const sendingRef = useRef(false)
  const prefill = location.state?.prefill

  const deliver = useCallback(async (content, optimisticId) => {
    sendingRef.current = true
    setSending(true)
    setError('')
    setFailedMessage(null)

    try {
      const reply = await sendMessage(conversationId, content)
      setMessages((prev) => [
        ...prev.map((message) =>
          message.id === optimisticId ? { ...message, deliveryState: 'sent' } : message
        ),
        reply,
      ])
    } catch (err) {
      setError(extractErrorMessage(err))
      setFailedMessage({ content, optimisticId })
      setMessages((prev) =>
        prev.map((message) =>
          message.id === optimisticId ? { ...message, deliveryState: 'failed' } : message
        )
      )
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }, [conversationId])

  const sendComposed = useCallback(async (content) => {
    if (!content || sendingRef.current) return
    const optimisticId = `pending-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      { id: optimisticId, role: 'user', content, created_at: new Date().toISOString(), deliveryState: 'sending' },
    ])
    await deliver(content, optimisticId)
  }, [deliver])

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

          // Check if there was a prefill topic from dashboard
          if (prefill && !prefillHandled.current && (!data.messages || data.messages.length === 0)) {
            prefillHandled.current = true
            sendComposed(prefill)
          }
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
  }, [conversationId, prefill, sendComposed])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function handleSend(event) {
    event.preventDefault()
    const content = draft.trim()
    if (!content) return
    setDraft('')
    await sendComposed(content)
  }

  async function handleRetry() {
    if (!failedMessage) return
    setMessages((prev) =>
      prev.map((message) =>
        message.id === failedMessage.optimisticId ? { ...message, deliveryState: 'sending' } : message
      )
    )
    await deliver(failedMessage.content, failedMessage.optimisticId)
  }

  return (
    <div className="chat-page">
      {/* Navigator Clinical Header */}
      <div className="chat-header">
        <button className="chat-back" onClick={() => navigate('/dashboard')} aria-label="Back to dashboard">
          ←
        </button>
        <div className="chat-header-info">
          <div className="chat-header-title-row">
            <h1>{conversation?.title || 'Care Navigator Consultation'}</h1>
            <span className="badge badge-accent">Verified Care Assistant</span>
          </div>
          <p className="chat-status">
            <span className="status-dot" aria-hidden="true" />
            Patient Navigator Active · Evidence-Attributed Guidance
          </p>
        </div>
      </div>

      {/* Safety & Clinical Scope Notice */}
      <div className="chat-safety-notice">
        <span className="notice-icon" aria-hidden="true">ℹ️</span>
        <p>
          NaviCare provides healthcare guidance, preparation instructions, and appointment scheduling assistance. NaviCare does not diagnose medical conditions. For life-threatening emergencies, call <strong>911</strong> immediately.
        </p>
      </div>

      {error && (
        <div className="alert-error chat-error">
          <span role="alert">{error}</span>
          {failedMessage && (
            <button type="button" className="chat-retry-link" onClick={handleRetry} disabled={sending}>
              Retry Message
            </button>
          )}
        </div>
      )}

      {/* Chat Window */}
      <div className="chat-window card">
        {loading && <p className="dashboard-muted chat-loading">Connecting to your patient navigator…</p>}

        {!loading && messages.length === 0 && (
          <div className="chat-empty-hub">
            <div className="chat-empty-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path d="M12 2 L20 5.5 V11 C20 16.5 16.5 20.5 12 22 C7.5 20.5 4 16.5 4 11 V5.5 L12 2Z" />
                <path d="M12 8 V14 M9 11 H15" />
              </svg>
            </div>
            <h2>How can NaviCare assist your care today?</h2>
            <p className="dashboard-muted">
              Select a common healthcare navigation topic below or type your question in the box.
            </p>

            <div className="chat-quick-starters">
              {QUICK_STARTERS.map((starter, index) => (
                <button
                  key={index}
                  className="quick-starter-btn"
                  onClick={() => sendComposed(starter.prompt)}
                  disabled={sending}
                >
                  <span className="starter-icon" aria-hidden="true">{starter.icon}</span>
                  <div className="starter-text">
                    <strong>{starter.title}</strong>
                    <span>{starter.prompt}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {!loading &&
          messages.map((message) => (
            <MessageBubble key={message.id} message={message} onQuickMessage={sendComposed} sending={sending} />
          ))}

        {sending && (
          <div className="chat-bubble-row assistant">
            <div className="chat-bubble assistant chat-typing" aria-label="NaviCare is reviewing your request">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Message Composer */}
      <form className="chat-composer" onSubmit={handleSend}>
        <label className="sr-only" htmlFor="chat-message">Message the care navigator</label>
        <input
          id="chat-message"
          type="text"
          placeholder="Ask about symptoms, medical prep, follow-ups, or booking…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={loading || sending}
        />
        <button className="btn btn-primary" type="submit" disabled={loading || sending || !draft.trim()}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
