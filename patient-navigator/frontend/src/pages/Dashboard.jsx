import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMyProfile } from '../api/patients'
import { createConversation, listConversations } from '../api/conversations'
import { cancelAppointment, listAppointments } from '../api/appointments'
import { completeFollowUp, createAppointmentReminder, listFollowUps } from '../api/followUps'
import { extractErrorMessage } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
import Icon from '../components/Icon'
import './dashboard.css'

const SUGGESTIONS = [
  { label: 'Book an appointment', prompt: 'I would like to find and schedule an appointment.' },
  { label: 'Prepare for a lab test', prompt: 'What instructions should I follow before having routine fasting blood work done?' },
  { label: 'Review my care tasks', prompt: 'Can you check my pending care tasks and tell me what follow-ups I need to complete?' },
  { label: 'Which specialist should I see?', prompt: 'I have a health concern and would like help working out which kind of specialist or clinic to see.' },
]

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function formatCurrentDate() {
  return new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
}

function parseAppointmentDate(isoString) {
  const date = new Date(isoString)
  return {
    month: date.toLocaleDateString(undefined, { month: 'short' }).toUpperCase(),
    day: date.getDate(),
    weekday: date.toLocaleDateString(undefined, { weekday: 'short' }),
    time: date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }),
    full: date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
    short: date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
  }
}

function SectionSkeleton({ rows = 2, height = 72 }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height }} />
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [profile, setProfile] = useState(null)
  const [conversations, setConversations] = useState([])
  const [appointments, setAppointments] = useState([])
  const [followUps, setFollowUps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sectionErrors, setSectionErrors] = useState({ appointments: '', tasks: '', conversations: '' })
  const [startingChat, setStartingChat] = useState(false)
  const [cancellingId, setCancellingId] = useState(null)
  const [reminderState, setReminderState] = useState({}) // appointmentId -> 'busy' | 'done'
  const [completingTaskId, setCompletingTaskId] = useState(null)
  const [appointmentToCancel, setAppointmentToCancel] = useState(null)
  const [taskToComplete, setTaskToComplete] = useState(null)
  const [askDraft, setAskDraft] = useState('')

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [profileResult, conversationResult, appointmentResult, followUpResult] = await Promise.allSettled([
          getMyProfile(),
          listConversations(),
          listAppointments('scheduled'),
          listFollowUps('pending'),
        ])
        if (!cancelled) {
          setProfile(profileResult.status === 'fulfilled' ? profileResult.value : null)
          setConversations(conversationResult.status === 'fulfilled' ? conversationResult.value || [] : [])
          setAppointments(appointmentResult.status === 'fulfilled' ? appointmentResult.value || [] : [])
          setFollowUps(followUpResult.status === 'fulfilled' ? followUpResult.value || [] : [])
          setSectionErrors({
            appointments: appointmentResult.status === 'rejected' ? 'Your appointment list could not be loaded. Please try again.' : '',
            tasks: followUpResult.status === 'rejected' ? 'Your care tasks could not be loaded. Please try again.' : '',
            conversations: conversationResult.status === 'rejected' ? 'Your previous consultations could not be loaded. Please try again.' : '',
          })
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

  async function handleStartChat(initialTopic) {
    setStartingChat(true)
    setError('')
    try {
      const conversation = await createConversation()
      if (initialTopic) {
        navigate(`/chat/${conversation.id}`, { state: { prefill: initialTopic } })
      } else {
        navigate(`/chat/${conversation.id}`)
      }
    } catch (err) {
      setError(extractErrorMessage(err))
      setStartingChat(false)
    }
  }

  function handleAskSubmit(event) {
    event.preventDefault()
    const topic = askDraft.trim()
    handleStartChat(topic || undefined)
  }

  async function handleCancelAppointment(id) {
    setCancellingId(id)
    try {
      await cancelAppointment(id)
      setAppointments((prev) => prev.filter((a) => a.id !== id))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setCancellingId(null)
      setAppointmentToCancel(null)
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

  async function handleCompleteTask(id) {
    setCompletingTaskId(id)
    try {
      await completeFollowUp(id)
      setFollowUps((prev) => prev.filter((f) => f.id !== id))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setCompletingTaskId(null)
      setTaskToComplete(null)
    }
  }

  const displayName = profile?.first_name || user?.username || 'there'
  const nextAppointment = appointments[0]
  const nextVisit = nextAppointment ? parseAppointmentDate(nextAppointment.start_time) : null

  const openTasks = followUps.length
  const summary = (() => {
    if (loading) return null
    const visit = nextVisit
      ? `Your next visit is ${nextVisit.short} at ${nextVisit.time} with ${nextAppointment.provider_name}.`
      : 'You have no visits booked.'
    const tasks =
      openTasks === 0
        ? 'Nothing on your care plan needs doing right now.'
        : `${openTasks} ${openTasks === 1 ? 'task is' : 'tasks are'} waiting on your care plan.`
    return `${visit} ${tasks}`
  })()

  return (
    <div className="page dashboard">
      <header className="dashboard-header">
        <p className="page-eyebrow">{formatCurrentDate()}</p>
        <h1 className="page-title">
          {getGreeting()}, {displayName}.
        </h1>
        {loading ? (
          <span className="skeleton dashboard-summary-skeleton" aria-hidden="true" />
        ) : (
          <p className="dashboard-summary">{summary}</p>
        )}
      </header>

      {error && (
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      )}

      {/* Ask the Navigator */}
      <section className="ask" aria-labelledby="ask-heading">
        <form className="ask-form" onSubmit={handleAskSubmit}>
          <label htmlFor="ask-input" id="ask-heading" className="ask-label">
            Ask the Navigator
            <span>Answers come from vetted sources and cite them. It can also book visits for you.</span>
          </label>
          <div className="ask-row">
            <input
              id="ask-input"
              type="text"
              placeholder="e.g. Do I need to fast before a blood test?"
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              disabled={startingChat}
              autoComplete="off"
            />
            <button type="submit" className="btn btn-primary ask-submit" disabled={startingChat}>
              {startingChat ? 'Starting…' : 'Ask'}
            </button>
          </div>
        </form>
        <div className="ask-suggestions">
          <span className="ask-suggestions-label">Or start with</span>
          {SUGGESTIONS.map((item) => (
            <button
              key={item.label}
              type="button"
              className="suggestion-link"
              onClick={() => handleStartChat(item.prompt)}
              disabled={startingChat}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      <div className="dashboard-grid">
        {/* Appointments */}
        <section aria-labelledby="appointments-heading">
          <div className="section-header">
            <h2 id="appointments-heading" className="section-title">Upcoming visits</h2>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleStartChat('I would like to find and schedule an appointment.')}
              disabled={startingChat}
            >
              <Icon name="plus" size={15} /> Book a visit
            </button>
          </div>

          {loading && <SectionSkeleton rows={2} height={88} />}

          {!loading && sectionErrors.appointments && (
            <div className="alert-error" role="alert">{sectionErrors.appointments}</div>
          )}

          {!loading && !sectionErrors.appointments && appointments.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">
                <Icon name="calendar" size={20} />
              </div>
              <h3>No visits booked</h3>
              <p>The Navigator can find an opening that suits you and book it for you.</p>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleStartChat('Find an available doctor for me.')}
                disabled={startingChat}
              >
                Find an appointment
              </button>
            </div>
          )}

          {!loading && !sectionErrors.appointments && appointments.length > 0 && (
            <ul className="list-group appointment-list">
              {appointments.map((appointment) => {
                const dateParts = parseAppointmentDate(appointment.start_time)
                return (
                  <li key={appointment.id} className="appointment-row">
                    <div className="date-block" aria-label={`Date: ${dateParts.full}`}>
                      <span className="date-block-day">{dateParts.day}</span>
                      <span className="date-block-month">{dateParts.month}</span>
                    </div>

                    <div className="appointment-body">
                      <div className="appointment-provider">{appointment.provider_name}</div>
                      <div className="appointment-meta">
                        <span>{appointment.department_name}</span>
                        <span className="dot-sep" aria-hidden="true" />
                        <span className="mono">
                          {dateParts.weekday} {dateParts.time}
                        </span>
                      </div>
                    </div>

                    <div className="appointment-actions">
                      {reminderState[appointment.id] === 'done' ? (
                        <span className="badge badge-success">
                          <Icon name="check" size={12} strokeWidth={2.4} /> Reminder set
                        </span>
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRemindMe(appointment.id)}
                          disabled={reminderState[appointment.id] === 'busy'}
                          title="Get a reminder 24 hours before"
                        >
                          <Icon name="bell" size={14} />
                          {reminderState[appointment.id] === 'busy' ? 'Setting…' : 'Remind me'}
                        </button>
                      )}
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleStartChat(`I need to reschedule my appointment with ${appointment.provider_name}.`)}
                      >
                        Reschedule
                      </button>
                      <button
                        className="btn btn-ghost-danger btn-sm"
                        onClick={() => setAppointmentToCancel(appointment)}
                        disabled={cancellingId === appointment.id}
                      >
                        {cancellingId === appointment.id ? 'Cancelling…' : 'Cancel'}
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        <aside className="dashboard-aside">
          {/* Care tasks */}
          <section aria-labelledby="tasks-heading">
            <div className="section-header">
              <h2 id="tasks-heading" className="section-title">Care plan</h2>
              <Link to="/follow-ups" className="section-link">
                See all <Icon name="chevronRight" size={14} />
              </Link>
            </div>

            {loading && <SectionSkeleton rows={2} height={56} />}

            {!loading && sectionErrors.tasks && (
              <div className="alert-error" role="alert">{sectionErrors.tasks}</div>
            )}

            {!loading && !sectionErrors.tasks && followUps.length === 0 && (
              <div className="empty-state compact">
                <div className="empty-icon">
                  <Icon name="check" size={20} />
                </div>
                <h3>Nothing to do right now</h3>
                <p>New tasks from your care team will show up here.</p>
              </div>
            )}

            {!loading && !sectionErrors.tasks && followUps.length > 0 && (
              <ul className="list-group task-list">
                {followUps.slice(0, 4).map((task) => (
                  <li key={task.id} className="task-row">
                    <button
                      type="button"
                      className="task-check"
                      onClick={() => setTaskToComplete(task)}
                      disabled={completingTaskId === task.id}
                      aria-label={`Mark “${task.title}” complete`}
                      title="Mark complete"
                    >
                      <Icon name="check" size={13} strokeWidth={2.6} />
                    </button>
                    <div className="task-body">
                      <span className="task-title">{task.title}</span>
                      {task.due_at && (
                        <span className="task-due">
                          <Icon name="clock" size={12} />
                          Due <span className="mono">{new Date(task.due_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Conversations */}
          <section aria-labelledby="conversations-heading">
            <div className="section-header">
              <h2 id="conversations-heading" className="section-title">Recent conversations</h2>
            </div>

            {loading && <SectionSkeleton rows={2} height={56} />}

            {!loading && sectionErrors.conversations && (
              <div className="alert-error" role="alert">{sectionErrors.conversations}</div>
            )}

            {!loading && !sectionErrors.conversations && conversations.length === 0 && (
              <div className="empty-state compact">
                <div className="empty-icon">
                  <Icon name="message" size={20} />
                </div>
                <h3>No conversations yet</h3>
                <p>Questions you ask the Navigator are kept here.</p>
              </div>
            )}

            {!loading && !sectionErrors.conversations && conversations.length > 0 && (
              <ul className="list-group">
                {conversations.slice(0, 4).map((conv) => (
                  <li key={conv.id}>
                    <button type="button" className="conversation-row" onClick={() => navigate(`/chat/${conv.id}`)}>
                      <span className="conversation-body">
                        <span className="conversation-title">{conv.title || 'Care conversation'}</span>
                        {conv.last_message && <span className="conversation-preview">{conv.last_message.content}</span>}
                      </span>
                      <Icon name="chevronRight" size={16} className="conversation-chevron" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>

      {appointmentToCancel && (
        <ConfirmDialog
          title="Cancel this appointment?"
          description={`This will remove your scheduled visit with ${appointmentToCancel.provider_name}. You may need to book another time with the care team.`}
          confirmLabel="Cancel appointment"
          danger
          busy={cancellingId === appointmentToCancel.id}
          onCancel={() => setAppointmentToCancel(null)}
          onConfirm={() => handleCancelAppointment(appointmentToCancel.id)}
        />
      )}

      {taskToComplete && (
        <ConfirmDialog
          title="Mark task complete?"
          description={`Mark “${taskToComplete.title}” as complete only after you have finished the requested care action.`}
          confirmLabel="Mark complete"
          busy={completingTaskId === taskToComplete.id}
          onCancel={() => setTaskToComplete(null)}
          onConfirm={() => handleCompleteTask(taskToComplete.id)}
        />
      )}
    </div>
  )
}
