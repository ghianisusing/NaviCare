import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { cancelFollowUp, completeFollowUp, listFollowUps } from '../api/followUps'
import { extractErrorMessage } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
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
  pending: 'Pending Action',
  completed: 'Completed',
  cancelled: 'Cancelled',
  expired: 'Overdue Task',
}

export default function FollowUps() {
  const [followUps, setFollowUps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [activeTab, setActiveTab] = useState('active') // 'active' | 'completed' | 'all'
  const [confirmation, setConfirmation] = useState(null)

  const load = useCallback(async () => {
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
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleComplete(id) {
    setBusyId(id)
    try {
      const updated = await completeFollowUp(id)
      setFollowUps((prev) => prev.map((f) => (f.id === id ? updated : f)))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusyId(null)
      setConfirmation(null)
    }
  }

  async function handleCancel(id) {
    setBusyId(id)
    try {
      await cancelFollowUp(id)
      setFollowUps((prev) => prev.map((f) => (f.id === id ? { ...f, status: 'cancelled' } : f)))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setBusyId(null)
      setConfirmation(null)
    }
  }

  const activeTasks = followUps.filter((f) => f.status === 'pending' || f.status === 'expired')
  const completedTasks = followUps.filter((f) => f.status === 'completed')

  let displayedTasks = followUps
  if (activeTab === 'active') {
    displayedTasks = activeTasks
  } else if (activeTab === 'completed') {
    displayedTasks = completedTasks
  }

  return (
    <div className="follow-ups-page">
      <div className="page-header">
        <div>
          <h1>Care Plan & Follow-up Tasks</h1>
          <p className="dashboard-subtitle">
            Personal health action items, lab preparations, and reminders tracked with your Patient Navigator.
          </p>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      {/* Tabs */}
      <div className="follow-ups-tabs" role="tablist" aria-label="Care task views">
        <button
          id="active-tasks-tab"
          type="button"
          role="tab"
          aria-selected={activeTab === 'active'}
          aria-controls="care-task-panel"
          className={`tab-btn ${activeTab === 'active' ? 'active' : ''}`}
          onClick={() => setActiveTab('active')}
        >
          Action Needed <span className="tab-counter">{activeTasks.length}</span>
        </button>
        <button
          id="completed-tasks-tab"
          type="button"
          role="tab"
          aria-selected={activeTab === 'completed'}
          aria-controls="care-task-panel"
          className={`tab-btn ${activeTab === 'completed' ? 'active' : ''}`}
          onClick={() => setActiveTab('completed')}
        >
          Completed <span className="tab-counter">{completedTasks.length}</span>
        </button>
        <button
          id="all-tasks-tab"
          type="button"
          role="tab"
          aria-selected={activeTab === 'all'}
          aria-controls="care-task-panel"
          className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => setActiveTab('all')}
        >
          All Records <span className="tab-counter">{followUps.length}</span>
        </button>
      </div>

      <div
        id="care-task-panel"
        role="tabpanel"
        aria-labelledby={`${activeTab}-tasks-tab`}
        tabIndex="0"
      >
        {loading && <p className="dashboard-muted">Retrieving your care tasks…</p>}

        {!loading && displayedTasks.length === 0 && (
        <div className="card empty-state">
          <div className="empty-icon" aria-hidden="true">📋</div>
          <h3>No tasks in this view</h3>
          <p className="dashboard-muted">
            {activeTab === 'active'
              ? 'You have completed all current care action items!'
              : 'No task records found in this category.'}
          </p>
          <Link to="/dashboard" className="btn btn-secondary btn-sm" style={{ marginTop: '6px' }}>
            Return to Dashboard
          </Link>
        </div>
      )}

        {!loading && displayedTasks.length > 0 && (
        <ul className="follow-up-list">
          {displayedTasks.map((followUp) => {
            const isResolved = followUp.status === 'completed' || followUp.status === 'cancelled'
            return (
              <li
                key={followUp.id}
                className={`card follow-up-card ${isResolved ? 'follow-up-card-resolved' : ''}`}
              >
                <div className="follow-up-content">
                  <div className="follow-up-badge-row">
                    <span
                      className={`badge ${
                        followUp.status === 'pending'
                          ? 'badge-warning'
                          : followUp.status === 'expired'
                          ? 'badge-danger'
                          : 'badge-neutral'
                      }`}
                    >
                      {STATUS_LABELS[followUp.status] || followUp.status}
                    </span>
                    {followUp.due_at && (
                      <span className="follow-up-due">
                        Due: {formatDate(followUp.due_at)}
                      </span>
                    )}
                  </div>

                  <h3 className="follow-up-title">{followUp.title}</h3>
                  {followUp.description && (
                    <p className="follow-up-description">{followUp.description}</p>
                  )}
                </div>

                {!isResolved && (
                  <div className="follow-up-actions">
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => setConfirmation({ type: 'complete', followUp })}
                      disabled={busyId === followUp.id}
                    >
                      {busyId === followUp.id ? 'Updating…' : '✓ Mark Complete'}
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setConfirmation({ type: 'cancel', followUp })}
                      disabled={busyId === followUp.id}
                    >
                      Cancel
                    </button>
                  </div>
                )}
                {isResolved && (
                  <span className="badge badge-success">✓ {STATUS_LABELS[followUp.status]}</span>
                )}
              </li>
            )
          })}
        </ul>
        )}
      </div>

      {confirmation && (
        <ConfirmDialog
          title={confirmation.type === 'complete' ? 'Mark task complete?' : 'Cancel this care task?'}
          description={
            confirmation.type === 'complete'
              ? `Mark “${confirmation.followUp.title}” as complete only after you have finished the requested care action.`
              : `Cancel “${confirmation.followUp.title}”? It will remain in your care history but will no longer be an active task.`
          }
          confirmLabel={confirmation.type === 'complete' ? 'Mark complete' : 'Cancel task'}
          danger={confirmation.type === 'cancel'}
          busy={busyId === confirmation.followUp.id}
          onCancel={() => setConfirmation(null)}
          onConfirm={() =>
            confirmation.type === 'complete'
              ? handleComplete(confirmation.followUp.id)
              : handleCancel(confirmation.followUp.id)
          }
        />
      )}
    </div>
  )
}
