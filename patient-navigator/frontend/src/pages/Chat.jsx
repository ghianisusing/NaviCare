import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getConversation, sendMessage } from '../api/conversations'
import { confirmAgentAction, declineAgentAction } from '../api/appointments'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
import './chat.css'

const URGENCY_LABELS = {
  emergency: 'Seek emergency care now',
  urgent: 'Prompt medical attention recommended',
}

const QUICK_STARTERS = [
  {
    icon: 'calendar',
    title: 'Schedule an appointment',
    prompt: 'Help me find and schedule an appointment with an available doctor this week.',
  },
  {
    icon: 'flask',
    title: 'Prepare for a lab test',
    prompt: 'What instructions should I follow before having routine fasting blood work done?',
  },
  {
    icon: 'tasks',
    title: 'Review my follow-ups',
    prompt: 'Can you check my pending care tasks and tell me what follow-ups I need to complete?',
  },
  {
    icon: 'stethoscope',
    title: 'Find the right specialist',
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
    return <p className="chat-card-empty">No available appointment slots matched that criteria.</p>
  }
  return (
    <div className="chat-card-group">
      <div className="chat-card-group-label">
        <Icon name="calendar" size={14} /> Available openings
      </div>
      <div className="chat-slot-grid">
        {slots.map((slot, index) => (
          <div key={index} className="chat-slot">
            <div className="chat-slot-time">{formatDateTime(slot.start_time)}</div>
            <div className="chat-slot-provider">{slot.provider_name}</div>
            <div className="chat-slot-department">{slot.department_name}</div>
            <button
              className="btn btn-secondary btn-sm chat-slot-select"
              disabled={disabled}
              onClick={() =>
                onSelect(`Book the appointment with ${slot.provider_name} on ${formatDateTime(slot.start_time)}.`)
              }
            >
              Choose this time
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function AppointmentList({ appointments }) {
  if (!appointments || appointments.length === 0) {
    return <p className="chat-card-empty">No appointments found.</p>
  }
  return (
    <ul className="chat-list">
      {appointments.map((appointment) => (
        <li key={appointment.id} className="chat-list-row">
          <span className="chat-list-icon">
            <Icon name="calendar" size={15} />
          </span>
          <div className="chat-list-body">
            <div className="chat-list-title">{appointment.provider_name}</div>
            <div className="chat-list-meta">
              {appointment.department_name} · {formatDateTime(appointment.start_time)}
            </div>
          </div>
          <span className="badge badge-success">{appointment.status}</span>
        </li>
      ))}
    </ul>
  )
}

function FollowUpList({ followUps }) {
  if (!followUps || followUps.length === 0) {
    return <p className="chat-card-empty">No follow-ups recorded.</p>
  }
  return (
    <ul className="chat-list">
      {followUps.map((followUp) => (
        <li key={followUp.id} className="chat-list-row">
          <span className="chat-list-icon">
            <Icon name="tasks" size={15} />
          </span>
          <div className="chat-list-body">
            <div className="chat-list-title">{followUp.title}</div>
            {followUp.due_at && <div className="chat-list-meta">Due {formatDateTime(followUp.due_at)}</div>}
          </div>
          <span className="badge badge-warning">{followUp.status}</span>
        </li>
      ))}
    </ul>
  )
}

function ReminderList({ reminders }) {
  if (!reminders || reminders.length === 0) {
    return <p className="chat-card-empty">No active reminders found.</p>
  }
  return (
    <ul className="chat-list">
      {reminders.map((reminder) => (
        <li key={reminder.id} className="chat-list-row">
          <span className="chat-list-icon">
            <Icon name="bell" size={15} />
          </span>
          <div className="chat-list-body">
            <div className="chat-list-title">{reminder.follow_up_title}</div>
            <div className="chat-list-meta">{formatDateTime(reminder.scheduled_for)}</div>
          </div>
          <span className="badge badge-neutral">{reminder.status}</span>
        </li>
      ))}
    </ul>
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
      <div className="chat-action-resolved confirmed">
        <Icon name="check" size={15} strokeWidth={2.4} /> Confirmed: {pendingAction.summary}
      </div>
    )
  }
  if (resolution === 'declined') {
    return <div className="chat-action-resolved">Cancelled. No changes were made to your schedule.</div>
  }

  return (
    <div className="chat-action-card">
      <div className="chat-action-label">Please confirm</div>
      <div className="chat-action-summary">{pendingAction.summary}</div>
      {resolution && <div className="alert-error chat-action-error">{resolution}</div>}
      <div className="chat-action-buttons">
        <button className="btn btn-primary btn-sm" onClick={handleConfirm} disabled={busy || disabled}>
          {busy ? 'Confirming…' : 'Confirm'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={handleDecline} disabled={busy || disabled}>
          Choose another
        </button>
      </div>
    </div>
  )
}

function MessageRich({ message, onQuickMessage, sending }) {
  const appointmentData = message.appointment_data
  const followUpData = message.follow_up_data
  return (
    <>
      {message.sources && message.sources.length > 0 && (
        <div className="chat-sources">
          <span className="chat-sources-label">Sources</span>
          <div className="chat-source-list">
            {message.sources.map((source, index) =>
              source.source_url ? (
                <a
                  key={index}
                  href={source.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="chat-source"
                  title={source.source || source.title}
                >
                  <Icon name="book" size={12} />
                  <span>{source.title}</span>
                  <Icon name="externalLink" size={11} />
                </a>
              ) : (
                <span key={index} className="chat-source" title={source.source || source.title}>
                  <Icon name="book" size={12} />
                  <span>{source.title}</span>
                </span>
              )
            )}
          </div>
        </div>
      )}

      {appointmentData?.type === 'slot_options' && (
        <SlotOptions slots={appointmentData.slots} onSelect={onQuickMessage} disabled={sending} />
      )}
      {appointmentData?.type === 'appointment_list' && <AppointmentList appointments={appointmentData.appointments} />}

      {followUpData?.type === 'follow_up_list' && <FollowUpList followUps={followUpData.follow_ups} />}
      {followUpData?.type === 'reminder_list' && <ReminderList reminders={followUpData.reminders} />}

      {message.pending_action && <PendingActionCard pendingAction={message.pending_action} disabled={sending} />}
    </>
  )
}

function Message({ message, onQuickMessage, sending }) {
  const urgency = message.urgency
  const isFlagged = urgency === 'emergency' || urgency === 'urgent'

  if (message.role === 'user') {
    return (
      <div className="msg msg-user">
        <div className={`msg-user-bubble ${message.deliveryState === 'sending' ? 'is-sending' : ''}`}>
          {message.content}
        </div>
        {message.deliveryState === 'failed' && (
          <span className="msg-failed" role="status">
            <Icon name="info" size={13} /> Not sent. Use “Retry” above to try again.
          </span>
        )}
      </div>
    )
  }

  if (message.role === 'system') {
    return <div className="msg msg-system">{message.content}</div>
  }

  const isStaff = message.role === 'staff'

  return (
    <div className={`msg msg-agent ${isStaff ? 'msg-staff' : ''}`}>
      <span className={`msg-avatar ${isStaff ? 'staff' : 'ai'}`} aria-hidden="true">
        <Icon name={isStaff ? 'headset' : 'sparkle'} size={15} />
      </span>
      <div className="msg-content">
        <div className="msg-author">
          {isStaff ? (
            <>
              Care Support <span className="badge badge-staff">Staff member</span>
            </>
          ) : (
            'Navigator'
          )}
        </div>

        {isFlagged && (
          <div className={`msg-urgency ${urgency}`} role="alert">
            <Icon name="alert" size={15} strokeWidth={2} />
            {URGENCY_LABELS[urgency]}
          </div>
        )}

        <div className={isStaff ? 'msg-staff-card' : undefined}>
          <p className="msg-text">{message.content}</p>
        </div>

        <MessageRich message={message} onQuickMessage={onQuickMessage} sending={sending} />
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
  const textareaRef = useRef(null)
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
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  // Grow the composer with its content, up to a limit.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [draft])

  async function handleSend(event) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || sending) return
    setDraft('')
    await sendComposed(content)
  }

  function handleComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
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

  const isEmpty = !loading && messages.length === 0

  return (
    <div className="chat-page">
      <header className="chat-header">
        <button className="icon-btn" onClick={() => navigate('/dashboard')} aria-label="Back to home">
          <Icon name="arrowLeft" size={18} />
        </button>
        <span className="msg-avatar ai chat-header-avatar" aria-hidden="true">
          <Icon name="sparkle" size={16} />
        </span>
        <div className="chat-header-info">
          <h1>{conversation?.title || 'New conversation'}</h1>
          <p className="chat-status">
            <span className="status-dot" aria-hidden="true" />
            Patient Navigator · answers cite their sources
          </p>
        </div>
      </header>

      <div className="chat-scroll">
        <div className="chat-thread">
          {error && (
            <div className="alert-error chat-error" role="alert">
              <Icon name="info" size={16} />
              <span className="chat-error-text">{error}</span>
              {failedMessage && (
                <button type="button" className="btn btn-secondary btn-sm" onClick={handleRetry} disabled={sending}>
                  Retry
                </button>
              )}
            </div>
          )}

          {loading && (
            <div className="chat-loading" aria-label="Loading conversation">
              <div className="skeleton" style={{ height: 44, width: '55%', alignSelf: 'flex-end' }} />
              <div className="skeleton" style={{ height: 88, width: '80%' }} />
            </div>
          )}

          {isEmpty && (
            <div className="chat-empty">
              <span className="chat-empty-mark" aria-hidden="true">
                <Icon name="sparkle" size={26} />
              </span>
              <h2>How can I help with your care today?</h2>
              <p>
                I can explain tests and procedures, help you work out where to go for care, and book or manage your
                appointments.
              </p>

              <div className="chat-starters">
                {QUICK_STARTERS.map((starter) => (
                  <button
                    key={starter.title}
                    className="chat-starter"
                    onClick={() => sendComposed(starter.prompt)}
                    disabled={sending}
                  >
                    <span className="chat-starter-icon">
                      <Icon name={starter.icon} size={16} />
                    </span>
                    <strong>{starter.title}</strong>
                    <span>{starter.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {!loading &&
            messages.map((message) => (
              <Message key={message.id} message={message} onQuickMessage={sendComposed} sending={sending} />
            ))}

          {sending && (
            <div className="msg msg-agent">
              <span className="msg-avatar ai" aria-hidden="true">
                <Icon name="sparkle" size={15} />
              </span>
              <div className="msg-content">
                <div className="chat-typing" role="status" aria-label="The Navigator is reviewing your request">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="chat-footer">
        <form className="chat-composer" onSubmit={handleSend}>
          <label className="sr-only" htmlFor="chat-message">Message the Navigator</label>
          <textarea
            id="chat-message"
            ref={textareaRef}
            rows={1}
            placeholder="Ask about symptoms, test prep, follow-ups or booking…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            disabled={loading}
          />
          <button
            className="chat-send"
            type="submit"
            disabled={loading || sending || !draft.trim()}
            aria-label={sending ? 'Sending' : 'Send message'}
          >
            <Icon name="arrowUp" size={18} strokeWidth={2.2} />
          </button>
        </form>
        <p className="chat-disclaimer">
          NaviCare offers guidance, not diagnosis. For a life-threatening emergency, call <strong>your local emergency number</strong>.
        </p>
      </div>
    </div>
  )
}
