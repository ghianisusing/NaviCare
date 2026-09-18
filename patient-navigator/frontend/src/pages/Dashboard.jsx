import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getMyProfile } from '../api/patients'
import { createConversation, listConversations } from '../api/conversations'
import { cancelAppointment, listAppointments } from '../api/appointments'
import { completeFollowUp, createAppointmentReminder, listFollowUps } from '../api/followUps'
import { extractErrorMessage } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
import './dashboard.css'

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
    year: 'numeric',
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
  }
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

  const displayName = profile?.first_name || user?.username || 'Patient'
  const nextAppointment = appointments[0]

  return (
    <div className="dashboard">
      {/* Patient Greeting & Status Banner */}
      <div className="dashboard-hero">
        <div className="dashboard-hero-content">
          <div className="dashboard-date-badge">
            <span aria-hidden="true">🗓️</span> {formatCurrentDate()}
          </div>
          <h1>
            {getGreeting()}, {displayName}
          </h1>
          <p className="dashboard-hero-subtitle">
            Welcome to your NaviCare patient portal. Review your upcoming care, follow-up instructions, and connect with your Patient Navigator.
          </p>
        </div>
        <div className="dashboard-hero-status card">
          <div className="status-item">
            <span className="status-label">Next Care Visit</span>
            <strong className="status-value">
              {nextAppointment
                ? `${parseAppointmentDate(nextAppointment.start_time).weekday}, ${parseAppointmentDate(nextAppointment.start_time).time}`
                : 'None scheduled'}
            </strong>
          </div>
          <div className="status-item">
            <span className="status-label">Action Tasks</span>
            <strong className="status-value">{followUps.length} pending</strong>
          </div>
          <div className="status-item">
            <span className="status-label">Care Record</span>
            <span className="badge badge-success">✓ Account Active</span>
          </div>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      {/* Quick Health Actions Grid */}
      <section className="dashboard-actions-grid" aria-label="Quick Actions">
        <button
          className="dashboard-action-card card primary-action"
          onClick={() => handleStartChat()}
          disabled={startingChat}
        >
          <div className="action-icon-wrap primary">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div className="action-text">
            <h3>{startingChat ? 'Connecting…' : 'Ask Care Navigator'}</h3>
            <p>Get answers to health questions, symptom navigation, or appointment guidance.</p>
          </div>
          <span className="action-arrow" aria-hidden="true">→</span>
        </button>

        <button
          className="dashboard-action-card card"
          onClick={() => handleStartChat('I would like to find and schedule an appointment.')}
          disabled={startingChat}
        >
          <div className="action-icon-wrap teal">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          </div>
          <div className="action-text">
            <h3>Find & Book Care</h3>
            <p>Browse department openings and book visits with clinical specialists.</p>
          </div>
          <span className="action-arrow" aria-hidden="true">→</span>
        </button>

        <Link to="/follow-ups" className="dashboard-action-card card">
          <div className="action-icon-wrap amber">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </div>
          <div className="action-text">
            <h3>Care Plan & Tasks</h3>
            <p>Track post-consultation tasks, lab test prep, and health reminders.</p>
          </div>
          <span className="action-arrow" aria-hidden="true">→</span>
        </Link>

        <Link to="/profile" className="dashboard-action-card card">
          <div className="action-icon-wrap slate">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <div className="action-text">
            <h3>My Health Profile</h3>
            <p>Review and update your demographic details and contact information.</p>
          </div>
          <span className="action-arrow" aria-hidden="true">→</span>
        </Link>
      </section>

      {/* Main Dashboard Grid: Appointments & Tasks */}
      <div className="dashboard-main-grid">
        {/* Upcoming Appointments Column */}
        <section className="dashboard-section appointments-section">
          <div className="section-header">
            <div>
              <h2>Upcoming Appointments</h2>
              <p className="section-subtitle">Your confirmed consultations and clinic visits</p>
            </div>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => handleStartChat('I would like to find and schedule an appointment.')}
              disabled={startingChat}
            >
              + Book Visit
            </button>
          </div>

          {loading && <p className="dashboard-muted">Checking scheduled appointments…</p>}

          {!loading && sectionErrors.appointments && (
            <div className="alert-error" role="alert">{sectionErrors.appointments}</div>
          )}

          {!loading && !sectionErrors.appointments && appointments.length === 0 && (
            <div className="card empty-state">
              <div className="empty-icon" aria-hidden="true">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              </div>
              <h3>No scheduled appointments</h3>
              <p className="dashboard-muted">You have no upcoming clinic or telehealth visits booked at this time.</p>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleStartChat('Find an available doctor for me.')}
                disabled={startingChat}
              >
                Schedule with Navigator
              </button>
            </div>
          )}

          {!loading && !sectionErrors.appointments && appointments.length > 0 && (
            <div className="appointment-list">
              {appointments.map((appointment) => {
                const dateParts = parseAppointmentDate(appointment.start_time)
                return (
                  <div key={appointment.id} className="card appointment-card">
                    <div className="appointment-date-badge" aria-label={`Date: ${dateParts.full}`}>
                      <span className="date-month">{dateParts.month}</span>
                      <span className="date-day">{dateParts.day}</span>
                      <span className="date-weekday">{dateParts.weekday}</span>
                    </div>

                    <div className="appointment-details">
                      <div className="appointment-tags">
                        <span className="badge badge-primary">{appointment.department_name}</span>
                        <span className="badge badge-success">Confirmed Visit</span>
                      </div>
                      <h4 className="appointment-provider">{appointment.provider_name}</h4>
                      <p className="appointment-time-info">
                        <strong>{dateParts.time}</strong> · In-Person Clinic Consult
                      </p>
                    </div>

                    <div className="appointment-actions">
                      {reminderState[appointment.id] === 'done' ? (
                        <span className="badge badge-accent appointment-reminder-set">
                          ✓ 24h Reminder Active
                        </span>
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRemindMe(appointment.id)}
                          disabled={reminderState[appointment.id] === 'busy'}
                          title="Set automated SMS/portal reminder 24 hours prior"
                        >
                          {reminderState[appointment.id] === 'busy' ? 'Setting…' : '⏰ Remind me'}
                        </button>
                      )}
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleStartChat(`I need to reschedule my appointment with ${appointment.provider_name}.`)}
                      >
                        Reschedule
                      </button>
                      <button
                        className="btn btn-secondary btn-sm appointment-cancel-btn"
                        onClick={() => setAppointmentToCancel(appointment)}
                        disabled={cancellingId === appointment.id}
                      >
                        {cancellingId === appointment.id ? 'Cancelling…' : 'Cancel'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>

        {/* Side Column: Follow-ups / Care Plan Action Items */}
        <aside className="dashboard-section tasks-aside">
          <div className="section-header">
            <div>
              <h2>Care Action Tasks</h2>
              <p className="section-subtitle">To-dos from your care team</p>
            </div>
            <Link to="/follow-ups" className="section-link">
              View all
            </Link>
          </div>

          {loading && <p className="dashboard-muted">Loading care plan…</p>}

          {!loading && sectionErrors.tasks && (
            <div className="alert-error" role="alert">{sectionErrors.tasks}</div>
          )}

          {!loading && !sectionErrors.tasks && followUps.length === 0 && (
            <div className="card empty-state small">
              <p>✓ All care action items are up to date.</p>
              <span className="dashboard-muted">New tasks assigned by your care navigator will appear here.</span>
            </div>
          )}

          {!loading && !sectionErrors.tasks && followUps.length > 0 && (
            <div className="dashboard-tasks-list">
              {followUps.slice(0, 4).map((task) => (
                <div key={task.id} className="card dashboard-task-card">
                  <div className="task-content">
                    <span className="badge badge-warning">Action Needed</span>
                    <strong className="task-title">{task.title}</strong>
                    {task.due_at && (
                      <span className="task-due">
                        Due: {new Date(task.due_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                      </span>
                    )}
                  </div>
                  <button
                    className="btn btn-secondary btn-sm task-done-btn"
                    onClick={() => setTaskToComplete(task)}
                    disabled={completingTaskId === task.id}
                    title="Mark this task as completed"
                  >
                    {completingTaskId === task.id ? '…' : 'Mark Done'}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Recent Navigator Conversations */}
          <div className="dashboard-conversations-block">
            <div className="section-header" style={{ marginTop: '28px' }}>
              <div>
                <h2>Care Consultations</h2>
                <p className="section-subtitle">Previous chats with your navigator</p>
              </div>
            </div>

            {!loading && sectionErrors.conversations && (
              <div className="alert-error" role="alert">{sectionErrors.conversations}</div>
            )}

            {!loading && !sectionErrors.conversations && conversations.length === 0 && (
              <div className="card empty-state small">
                <p>No previous conversations.</p>
                <span className="dashboard-muted">Ask a question anytime.</span>
              </div>
            )}

            {!loading && !sectionErrors.conversations && conversations.length > 0 && (
              <div className="conversation-list">
                {conversations.slice(0, 3).map((conv) => (
                  <button
                    key={conv.id}
                    className="conversation-row"
                    onClick={() => navigate(`/chat/${conv.id}`)}
                  >
                    <div className="conv-title-row">
                      <span className="conversation-title">{conv.title || 'General Care Navigation'}</span>
                      <span className="conv-arrow">→</span>
                    </div>
                    {conv.last_message && (
                      <span className="conversation-preview">{conv.last_message.content}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
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
