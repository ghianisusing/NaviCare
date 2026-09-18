import { useCallback, useEffect, useState } from 'react'
import { listNotifications, markNotificationRead } from '../api/notifications'
import { extractErrorMessage } from '../api/client'
import './notifications.css'

function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function getNotificationIcon(title = '') {
  const lower = title.toLowerCase()
  if (lower.includes('appointment') || lower.includes('visit') || lower.includes('schedule')) return '🗓️'
  if (lower.includes('reminder') || lower.includes('alert')) return '⏰'
  if (lower.includes('follow-up') || lower.includes('task')) return '📋'
  return '🩺'
}

export default function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all') // 'all' | 'unread'
  const [markingAll, setMarkingAll] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listNotifications()
      setNotifications(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleMarkRead(id) {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
    try {
      await markNotificationRead(id)
      window.dispatchEvent(new Event('notifications:updated'))
    } catch (err) {
      setError(extractErrorMessage(err))
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: false } : n)))
    }
  }

  async function handleMarkAllRead() {
    const unread = notifications.filter((n) => !n.read)
    if (unread.length === 0) return
    setMarkingAll(true)
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    try {
      const results = await Promise.allSettled(unread.map((n) => markNotificationRead(n.id)))
      const failedIds = new Set(
        results.flatMap((result, index) => (result.status === 'rejected' ? [unread[index].id] : []))
      )
      if (failedIds.size > 0) {
        setError('Some notifications could not be marked as read. Please try again.')
        setNotifications((prev) => prev.map((n) => (failedIds.has(n.id) ? { ...n, read: false } : n)))
      }
      if (failedIds.size < unread.length) {
        window.dispatchEvent(new Event('notifications:updated'))
      }
    } finally {
      setMarkingAll(false)
    }
  }

  const unreadCount = notifications.filter((n) => !n.read).length
  const displayed = filter === 'unread' ? notifications.filter((n) => !n.read) : notifications

  return (
    <div className="notifications-page">
      <div className="page-header-row">
        <div>
          <h1>Care Notifications</h1>
          <p className="dashboard-subtitle">
            Automated alerts, appointment reminders, and follow-up notices from your care team.
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleMarkAllRead}
            disabled={markingAll}
          >
            {markingAll ? 'Updating…' : '✓ Mark All as Read'}
          </button>
        )}
      </div>

      <div className="notifications-filter-bar">
        <button
          className={`filter-chip ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All Notifications ({notifications.length})
        </button>
        <button
          className={`filter-chip ${filter === 'unread' ? 'active' : ''}`}
          onClick={() => setFilter('unread')}
        >
          Unread Only ({unreadCount})
        </button>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {loading && <p className="dashboard-muted">Checking for care alerts…</p>}

      {!loading && displayed.length === 0 && (
        <div className="card empty-state">
          <div className="empty-icon" aria-hidden="true">🔔</div>
          <h3>No notifications</h3>
          <p className="dashboard-muted">
            {filter === 'unread' ? 'You have read all of your care notices.' : 'No notifications in your record.'}
          </p>
        </div>
      )}

      {!loading && displayed.length > 0 && (
        <ul className="notification-list">
          {displayed.map((notification) => (
            <li
              key={notification.id}
              className={`card notification-card ${notification.read ? 'notification-read' : 'notification-unread'}`}
            >
              <div className="notification-icon-wrap" aria-hidden="true">
                {getNotificationIcon(notification.title)}
              </div>

              <div className="notification-body">
                <div className="notification-header">
                  <span className="notification-title">{notification.title}</span>
                  <span className="notification-time">{timeAgo(notification.created_at)}</span>
                </div>
                <p className="notification-message">{notification.message}</p>
              </div>

              {!notification.read && (
                <button
                  className="btn btn-secondary btn-sm notif-read-btn"
                  onClick={() => handleMarkRead(notification.id)}
                  title="Mark as read"
                >
                  Mark read
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
