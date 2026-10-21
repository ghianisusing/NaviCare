import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { assignEscalation, getEscalation, resolveEscalation, respondToEscalation } from '../api/escalations'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
import './care-support.css'

export default function CareSupportDetail() {
  const { escalationId } = useParams()
  const navigate = useNavigate()

  const [escalation, setEscalation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [responseDraft, setResponseDraft] = useState('')
  const [sentCount, setSentCount] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getEscalation(escalationId)
      setEscalation(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [escalationId])

  useEffect(() => {
    load()
  }, [load])

  async function handleClaim() {
    setBusy(true)
    setError('')
    try {
      const updated = await assignEscalation(escalationId)
      setEscalation(updated)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRespond(event) {
    event.preventDefault()
    const content = responseDraft.trim()
    if (!content) return
    setBusy(true)
    setError('')
    try {
      await respondToEscalation(escalationId, content)
      setResponseDraft('')
      setSentCount((c) => c + 1)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleResolve() {
    setBusy(true)
    setError('')
    try {
      const updated = await resolveEscalation(escalationId)
      setEscalation(updated)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const backLink = (
    <button className="back-link" onClick={() => navigate('/care-support')}>
      <Icon name="arrowLeft" size={16} /> Care support
    </button>
  )

  if (loading && !escalation) {
    return (
      <div className="page" aria-label="Loading escalation">
        {backLink}
        <div className="skeleton" style={{ height: 64 }} />
        <div className="skeleton" style={{ height: 260 }} />
      </div>
    )
  }

  if (!escalation) {
    return (
      <div className="page">
        {backLink}
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error || 'Not found.'}
        </div>
      </div>
    )
  }

  const summary = escalation.summary || {}
  const isActive = escalation.status === 'assigned' || escalation.status === 'in_progress'
  const statusText = escalation.status.replace(/_/g, ' ')
  const statusBadge = isActive ? 'badge-primary' : escalation.status === 'resolved' ? 'badge-success' : 'badge-warning'

  return (
    <div className="page care-support-detail-page">
      {backLink}

      <header className="page-header">
        <div>
          <p className="page-eyebrow">Escalation #{escalation.id}</p>
          <h1 className="page-title">{escalation.patient_name}</h1>
          <div className="detail-meta">
            <span className={`badge badge-dot ${statusBadge}`}>
              {statusText.charAt(0).toUpperCase() + statusText.slice(1)}
            </span>
            {escalation.assigned_to_username && (
              <span className="muted">Assigned to {escalation.assigned_to_username}</span>
            )}
          </div>
        </div>
        <div className="detail-actions">
          {escalation.status === 'pending' && (
            <button className="btn btn-primary" onClick={handleClaim} disabled={busy}>
              Claim escalation
            </button>
          )}
          {isActive && (
            <button className="btn btn-secondary" onClick={handleResolve} disabled={busy}>
              <Icon name="check" size={15} /> Mark resolved
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      )}
      {sentCount > 0 && (
        <div className="alert-success" role="status">
          <Icon name="check" size={16} strokeWidth={2.4} />
          Response sent to the patient.
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-main">
          <section className="card detail-card">
            <h2 className="section-title">Internal summary</h2>
            <p className="detail-summary">{summary.summary}</p>

            {summary.relevant_appointments?.length > 0 && (
              <div className="detail-group">
                <h3>Relevant appointments</h3>
                <ul className="detail-list">
                  {summary.relevant_appointments.map((a) => (
                    <li key={a.id}>
                      <Icon name="calendar" size={14} />
                      <span>
                        <strong>{a.provider_name}</strong> · {a.department_name} · {new Date(a.start_time).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summary.relevant_follow_ups?.length > 0 && (
              <div className="detail-group">
                <h3>Relevant follow-ups</h3>
                <ul className="detail-list">
                  {summary.relevant_follow_ups.map((f) => (
                    <li key={f.id}>
                      <Icon name="tasks" size={14} />
                      <span>{f.title}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summary.agent_actions?.length > 0 && (
              <div className="detail-group">
                <h3>Recent agent actions</h3>
                <ul className="detail-list">
                  {summary.agent_actions.map((a, i) => (
                    <li key={i}>
                      <Icon name="sparkle" size={14} />
                      <span>
                        <code>{a.tool_name}</code> · {a.status}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {isActive && (
            <form className="card reply-card" onSubmit={handleRespond}>
              <label htmlFor="staff-reply" className="reply-label">
                Reply to {escalation.patient_name}
              </label>
              <textarea
                id="staff-reply"
                placeholder="Write your reply…"
                value={responseDraft}
                onChange={(e) => setResponseDraft(e.target.value)}
                rows={4}
              />
              <div className="reply-footer">
                <span className="field-hint">The patient sees this labelled as a message from Care Support staff.</span>
                <button className="btn btn-primary" type="submit" disabled={busy || !responseDraft.trim()}>
                  Send reply
                </button>
              </div>
            </form>
          )}
        </div>

        {escalation.events?.length > 0 && (
          <aside className="card detail-card">
            <h2 className="section-title">Activity</h2>
            <ol className="timeline">
              {escalation.events.map((event) => (
                <li key={event.id}>
                  <span className="timeline-dot" aria-hidden="true" />
                  <span className="timeline-action">{event.action.replace(/_/g, ' ')}</span>
                  <span className="timeline-meta">
                    {event.actor_username || 'system'} · {new Date(event.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ol>
          </aside>
        )}
      </div>
    </div>
  )
}
