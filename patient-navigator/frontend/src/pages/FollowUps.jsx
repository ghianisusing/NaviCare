import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { cancelFollowUp, completeFollowUp, listFollowUps } from '../api/followUps'
import { extractErrorMessage } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
import Icon from '../components/Icon'
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
  pending: 'To do',
  completed: 'Completed',
  cancelled: 'Cancelled',
  expired: 'Overdue',
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

  const TABS = [
    { id: 'active', label: 'To do', count: activeTasks.length },
    { id: 'completed', label: 'Completed', count: completedTasks.length },
    { id: 'all', label: 'All', count: followUps.length },
  ]

  return (
    <div className="page follow-ups-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Care plan</h1>
          <p className="page-subtitle">Tasks, test preparation and reminders from your care team.</p>
        </div>
      </header>

      {error && (
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      )}

      <div className="segmented" role="tablist" aria-label="Care task views">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`${tab.id}-tasks-tab`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls="care-task-panel"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label} <span className="count">{tab.count}</span>
          </button>
        ))}
      </div>

      <div id="care-task-panel" role="tabpanel" aria-labelledby={`${activeTab}-tasks-tab`} tabIndex="0" className="tab-panel">
        {loading && (
          <div className="skeleton-stack" aria-hidden="true">
            <div className="skeleton" style={{ height: 76 }} />
            <div className="skeleton" style={{ height: 76 }} />
            <div className="skeleton" style={{ height: 76 }} />
          </div>
        )}

        {!loading && displayedTasks.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">
              <Icon name={activeTab === 'active' ? 'check' : 'tasks'} size={20} />
            </div>
            <h3>{activeTab === 'active' ? "You're all caught up" : 'Nothing here yet'}</h3>
            <p>
              {activeTab === 'active'
                ? 'You have finished every care task. New ones from your care team will appear here.'
                : 'No tasks in this view.'}
            </p>
            <Link to="/dashboard" className="btn btn-secondary btn-sm">
              Back to home
            </Link>
          </div>
        )}

        {!loading && displayedTasks.length > 0 && (
          <ul className="list-group follow-up-list">
            {displayedTasks.map((followUp) => {
              const isResolved = followUp.status === 'completed' || followUp.status === 'cancelled'
              const isOverdue = followUp.status === 'expired'
              return (
                <li key={followUp.id} className={`follow-up-row ${isResolved ? 'is-resolved' : ''}`}>
                  <button
                    type="button"
                    className={`task-check ${followUp.status === 'completed' ? 'is-done' : ''}`}
                    onClick={() => setConfirmation({ type: 'complete', followUp })}
                    disabled={isResolved || busyId === followUp.id}
                    aria-label={isResolved ? STATUS_LABELS[followUp.status] : `Mark “${followUp.title}” complete`}
                    title={isResolved ? STATUS_LABELS[followUp.status] : 'Mark complete'}
                  >
                    <Icon name={followUp.status === 'cancelled' ? 'x' : 'check'} size={13} strokeWidth={2.6} />
                  </button>

                  <div className="follow-up-body">
                    <h3 className="follow-up-title">{followUp.title}</h3>
                    {followUp.description && <p className="follow-up-description">{followUp.description}</p>}
                    <div className="follow-up-meta">
                      {isOverdue && <span className="badge badge-danger">Overdue</span>}
                      {isResolved && (
                        <span className={`badge ${followUp.status === 'completed' ? 'badge-success' : 'badge-neutral'}`}>
                          {STATUS_LABELS[followUp.status]}
                        </span>
                      )}
                      {followUp.due_at && (
                        <span className={`follow-up-due ${isOverdue ? 'is-overdue' : ''}`}>
                          <Icon name="clock" size={13} />
                          Due {formatDate(followUp.due_at)}
                        </span>
                      )}
                    </div>
                  </div>

                  {!isResolved && (
                    <div className="follow-up-actions">
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setConfirmation({ type: 'complete', followUp })}
                        disabled={busyId === followUp.id}
                      >
                        {busyId === followUp.id ? 'Updating…' : 'Mark complete'}
                      </button>
                      <button
                        className="btn btn-ghost-danger btn-sm"
                        onClick={() => setConfirmation({ type: 'cancel', followUp })}
                        disabled={busyId === followUp.id}
                      >
                        Cancel
                      </button>
                    </div>
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
