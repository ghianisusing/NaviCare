import { useEffect, useState } from 'react'
import { cancelFollowUp, completeFollowUp, listFollowUps } from '../api/followUps'
import { extractErrorMessage } from '../api/client'
import './follow-ups.css'

function formatDate(isoString) {
  if (!isoString) return null
  return new Date(isoString).toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

const STATUS_LABELS = {
  pending: 'Pending',
  completed: 'Completed',
  cancelled: 'Cancelled',
  expired: 'Overdue',
}

export default function FollowUps() {
  const [followUps, setFollowUps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await listFollowUps()
      setFollowUps(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleComplete(id) {
    setBusyId(id)
    try {
      const updated = await completeFollowUp(id)
      setFollowUps((prev) => prev.map((f) => (f.id === id ? updated : f)))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function handleCancel(id) {
    if (!window.confirm('Cancel this follow-up?')) return
    setBusyId(id)
    try {
      await cancelFollowUp(id)
      setFollowUps((prev) => prev.map((f) => (f.id === id ? { ...f, status: 'cancelled' } : f)))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const pending = followUps.filter((f) => f.status === 'pending' || f.status === 'expired')
  const resolved = followUps.filter((f) => f.status === 'completed' || f.status === 'cancelled')

  return (
    <div className="follow-ups-page">
      <h1>Follow-ups</h1>
      <p className="dashboard-subtitle">Navigation tasks and reminders you've asked NaviCare to track.</p>

      {error && <div className="alert-error">{error}</div>}
      {loading && <p className="dashboard-muted">Loading…</p>}

      {!loading && pending.length === 0 && resolved.length === 0 && (
        <div className="card empty-state">
          <p>No follow-ups yet.</p>
          <p className="dashboard-muted">Ask NaviCare to remind you about something, and it'll show up here.</p>
        </div>
      )}

      {!loading && pending.length > 0 && (
        <ul className="follow-up-list">
          {pending.map((followUp) => (
            <li key={followUp.id} className="card follow-up-card">
              <div>
                <div className={`follow-up-status-badge status-${followUp.status}`}>
                  {STATUS_LABELS[followUp.status]}
                </div>
                <div className="follow-up-title">{followUp.title}</div>
                {followUp.description && <div className="follow-up-description">{followUp.description}</div>}
                {followUp.due_at && <div className="follow-up-due">Due: {formatDate(followUp.due_at)}</div>}
              </div>
              <div className="follow-up-actions">
                <button className="btn btn-primary" onClick={() => handleComplete(followUp.id)} disabled={busyId === followUp.id}>
                  Mark Complete
                </button>
                <button className="btn btn-secondary" onClick={() => handleCancel(followUp.id)} disabled={busyId === followUp.id}>
                  Cancel
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {!loading && resolved.length > 0 && (
        <>
          <h2 className="follow-ups-section-title">Past follow-ups</h2>
          <ul className="follow-up-list">
            {resolved.map((followUp) => (
              <li key={followUp.id} className="card follow-up-card follow-up-card-resolved">
                <div>
                  <div className={`follow-up-status-badge status-${followUp.status}`}>
                    {STATUS_LABELS[followUp.status]}
                  </div>
                  <div className="follow-up-title">{followUp.title}</div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
