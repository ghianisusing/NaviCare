import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listEscalations } from '../api/escalations'
import { extractErrorMessage } from '../api/client'
import './care-support.css'

const STATUS_LABELS = {
  pending: 'Pending',
  assigned: 'Assigned',
  in_progress: 'In Progress',
  resolved: 'Resolved',
  cancelled: 'Cancelled',
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
    <div className="care-support-page">
      <h1>Care Support</h1>
      <p className="dashboard-subtitle">Escalations awaiting a human care coordinator.</p>

      <div className="care-support-overview">
        <div className="care-support-stat">
          <span className="care-support-stat-value">{counts.pending}</span>
          <span className="care-support-stat-label">Pending</span>
        </div>
        <div className="care-support-stat">
          <span className="care-support-stat-value">{counts.in_progress}</span>
          <span className="care-support-stat-label">In Progress</span>
        </div>
        <div className="care-support-stat">
          <span className="care-support-stat-value">{counts.resolved}</span>
          <span className="care-support-stat-label">Resolved</span>
        </div>
      </div>

      <div className="care-support-filters">
        {['', 'pending', 'assigned', 'in_progress', 'resolved'].map((value) => (
          <button
            key={value || 'all'}
            className={`care-support-filter-btn ${statusFilter === value ? 'active' : ''}`}
            onClick={() => setStatusFilter(value)}
          >
            {value ? STATUS_LABELS[value] : 'All'}
          </button>
        ))}
      </div>

      {error && <div className="alert-error">{error}</div>}
      {loading && <p className="dashboard-muted">Loading…</p>}

      {!loading && escalations.length === 0 && (
        <div className="card empty-state">
          <p>No escalations here.</p>
        </div>
      )}

      {!loading && escalations.length > 0 && (
        <ul className="escalation-list">
          {escalations.map((escalation) => (
            <li key={escalation.id} className="card escalation-card">
              <div>
                <div className={`escalation-priority-badge priority-${escalation.priority}`}>
                  {escalation.priority === 'high' ? 'High Priority' : 'Normal'}
                </div>
                <div className="escalation-reason">{REASON_LABELS[escalation.reason] || escalation.reason}</div>
                <div className="escalation-patient">{escalation.patient_name}</div>
                <div className="escalation-meta">
                  {STATUS_LABELS[escalation.status]}
                  {escalation.assigned_to_username && ` · ${escalation.assigned_to_username}`}
                  {' · '}
                  {new Date(escalation.created_at).toLocaleString()}
                </div>
              </div>
              <Link className="btn btn-primary" to={`/care-support/${escalation.id}`}>
                Open
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
