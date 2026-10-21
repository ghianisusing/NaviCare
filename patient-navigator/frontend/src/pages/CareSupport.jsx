import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listEscalations } from '../api/escalations'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
import './care-support.css'

const STATUS_LABELS = {
  pending: 'Pending',
  assigned: 'Assigned',
  in_progress: 'In Progress',
  resolved: 'Resolved',
  cancelled: 'Cancelled',
}

const STATUS_BADGE = {
  pending: 'badge-warning',
  assigned: 'badge-primary',
  in_progress: 'badge-primary',
  resolved: 'badge-success',
  cancelled: 'badge-neutral',
}

const REASON_LABELS = {
  patient_request: 'Patient Request',
  out_of_scope: 'Out of Scope',
  repeated_failure: 'Repeated Failure',
  safety_review: 'Safety Review',
  administrative_issue: 'Administrative Issue',
  human_assistance_required: 'Human Assistance Required',
}

export default function CareSupport() {
  const [escalations, setEscalations] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await listEscalations(statusFilter ? { status: statusFilter } : {})
        if (!cancelled) setEscalations(data)
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
  }, [statusFilter])

  const counts = {
    pending: escalations.filter((e) => e.status === 'pending').length,
    in_progress: escalations.filter((e) => e.status === 'in_progress' || e.status === 'assigned').length,
    resolved: escalations.filter((e) => e.status === 'resolved').length,
  }

  return (
    <div className="page care-support-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Care support</h1>
          <p className="page-subtitle">Conversations the Navigator handed over to a person.</p>
        </div>
      </header>

      <section className="stat-grid" aria-label="Queue overview">
        <div className="stat-tile">
          <span className="stat-label">
            <span className="legend-dot warning" /> Waiting
          </span>
          <span className="stat-value">{counts.pending}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">
            <span className="legend-dot primary" /> In progress
          </span>
          <span className="stat-value">{counts.in_progress}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">
            <span className="legend-dot success" /> Resolved
          </span>
          <span className="stat-value">{counts.resolved}</span>
        </div>
      </section>

      <div className="segmented" role="group" aria-label="Filter by status">
        {['', 'pending', 'assigned', 'in_progress', 'resolved'].map((value) => (
          <button
            key={value || 'all'}
            className={statusFilter === value ? 'active' : ''}
            aria-pressed={statusFilter === value}
            onClick={() => setStatusFilter(value)}
          >
            {value ? STATUS_LABELS[value] : 'All'}
          </button>
        ))}
      </div>

      {error && (
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      )}

      {loading && (
        <div className="skeleton-stack" aria-hidden="true">
          <div className="skeleton" style={{ height: 72 }} />
          <div className="skeleton" style={{ height: 72 }} />
          <div className="skeleton" style={{ height: 72 }} />
        </div>
      )}

      {!loading && escalations.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">
            <Icon name="inbox" size={20} />
          </div>
          <h3>The queue is clear</h3>
          <p>No escalations match this filter right now.</p>
        </div>
      )}

      {!loading && escalations.length > 0 && (
        <ul className="list-group escalation-list">
          {escalations.map((escalation) => (
            <li key={escalation.id}>
              <Link className="escalation-row" to={`/care-support/${escalation.id}`}>
                <span className={`priority-bar priority-${escalation.priority}`} aria-hidden="true" />
                <div className="escalation-body">
                  <div className="escalation-title-row">
                    <span className="escalation-patient">{escalation.patient_name}</span>
                    {escalation.priority === 'high' && <span className="badge badge-danger">High priority</span>}
                  </div>
                  <div className="escalation-meta">
                    <span>{REASON_LABELS[escalation.reason] || escalation.reason}</span>
                    <span className="dot-sep" aria-hidden="true" />
                    <span>
                      {new Date(escalation.created_at).toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      })}
                    </span>
                    {escalation.assigned_to_username && (
                      <>
                        <span className="dot-sep" aria-hidden="true" />
                        <span>{escalation.assigned_to_username}</span>
                      </>
                    )}
                  </div>
                </div>
                <span className={`badge escalation-status ${STATUS_BADGE[escalation.status] || 'badge-neutral'}`}>
                  {STATUS_LABELS[escalation.status] || escalation.status}
                </span>
                <Icon name="chevronRight" size={16} className="row-chevron" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
