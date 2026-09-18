import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { assignEscalation, getEscalation, resolveEscalation, respondToEscalation } from '../api/escalations'
import { extractErrorMessage } from '../api/client'
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

  if (loading) return <p className="dashboard-muted">Loading…</p>
  if (!escalation) return <div className="alert-error">{error || 'Not found.'}</div>

  const summary = escalation.summary || {}
  const isActive = escalation.status === 'assigned' || escalation.status === 'in_progress'

  return (
    <div className="care-support-detail-page">
      <button className="chat-back" onClick={() => navigate('/care-support')} aria-label="Back to queue">
        ←
      </button>

      <h1>Escalation #{escalation.id}</h1>
      <p className="dashboard-subtitle">
        {escalation.patient_name} · {escalation.status}
        {escalation.assigned_to_username && ` · ${escalation.assigned_to_username}`}
      </p>

      {error && <div className="alert-error">{error}</div>}
      {sentCount > 0 && <div className="alert-success">Response sent to the patient.</div>}

      <div className="card escalation-summary-card">
        <h2>Internal summary</h2>
        <p>{summary.summary}</p>

        {summary.relevant_appointments?.length > 0 && (
          <>
            <h3>Relevant appointments</h3>
            <ul>
              {summary.relevant_appointments.map((a) => (
                <li key={a.id}>
                  {a.provider_name} — {a.department_name} — {new Date(a.start_time).toLocaleString()}
                </li>
              ))}
            </ul>
          </>
        )}

        {summary.relevant_follow_ups?.length > 0 && (
          <>
            <h3>Relevant follow-ups</h3>
            <ul>
              {summary.relevant_follow_ups.map((f) => (
                <li key={f.id}>{f.title}</li>
              ))}
            </ul>
          </>
        )}

        {summary.agent_actions?.length > 0 && (
          <>
            <h3>Recent agent actions</h3>
            <ul>
              {summary.agent_actions.map((a, i) => (
                <li key={i}>
                  {a.tool_name} — {a.status}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="care-support-actions">
        {escalation.status === 'pending' && (
          <button className="btn btn-primary" onClick={handleClaim} disabled={busy}>
            Claim
          </button>
        )}
        {isActive && (
          <button className="btn btn-secondary" onClick={handleResolve} disabled={busy}>
            Mark Resolved
          </button>
        )}
      </div>

      {isActive && (
        <form className="care-support-response-form" onSubmit={handleRespond}>
          <textarea
            placeholder="Respond to the patient…"
            value={responseDraft}
            onChange={(e) => setResponseDraft(e.target.value)}
            rows={3}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !responseDraft.trim()}>
            Send response
          </button>
        </form>
      )}

      {escalation.events?.length > 0 && (
        <section className="recent-section">
          <h2 className="escalation-audit-title">Audit trail</h2>
          <ul className="escalation-audit-list">
            {escalation.events.map((event) => (
              <li key={event.id}>
                <span className="escalation-audit-action">{event.action.replace(/_/g, ' ')}</span>
                <span className="escalation-audit-meta">
                  {event.actor_username || 'system'} · {new Date(event.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
