import { useCallback, useEffect, useState } from 'react'
import { listNotifications, markNotificationRead } from '../api/notifications'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
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
  if (lower.includes('appointment') || lower.includes('visit') || lower.includes('schedule')) return 'calendar'
  if (lower.includes('reminder') || lower.includes('alert')) return 'clock'
  if (lower.includes('follow-up') || lower.includes('task')) return 'tasks'
  if (lower.includes('support') || lower.includes('staff')) return 'headset'
  return 'bell'
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
    <div className="page notifications-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">Appointment reminders, follow-up notices and updates from your care team.</p>
        </div>
        {unreadCount > 0 && (
          <button className="btn btn-secondary btn-sm" onClick={handleMarkAllRead} disabled={markingAll}>
            <Icon name="check" size={15} />
            {markingAll ? 'Updating…' : 'Mark all as read'}
          </button>
        )}
      </header>

      <div className="segmented" role="group" aria-label="Filter notifications">
        <button className={filter === 'all' ? 'active' : ''} aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
          All <span className="count">{notifications.length}</span>
        </button>
        <button className={filter === 'unread' ? 'active' : ''} aria-pressed={filter === 'unread'} onClick={() => setFilter('unread')}>
          Unread <span className="count">{unreadCount}</span>
        </button>
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

      {!loading && displayed.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">
            <Icon name="inbox" size={20} />
          </div>
          <h3>{filter === 'unread' ? "You're all caught up" : 'No notifications yet'}</h3>
          <p>
            {filter === 'unread'
              ? 'You have read every notification.'
              : 'Reminders and updates from your care team will show up here.'}
          </p>
        </div>
      )}

      {!loading && displayed.length > 0 && (
        <ul className="list-group notification-list">
          {displayed.map((notification) => (
            <li key={notification.id} className={`notification-row ${notification.read ? 'is-read' : 'is-unread'}`}>
              <span className="notification-icon">
                <Icon name={getNotificationIcon(notification.title)} size={16} />
              </span>

              <div className="notification-body">
                <div className="notification-header">
                  <span className="notification-title">{notification.title}</span>
                  <span className="notification-time">{timeAgo(notification.created_at)}</span>
                </div>
                <p className="notification-message">{notification.message}</p>
              </div>

              {!notification.read && (
                <button
                  className="btn btn-ghost btn-sm notification-read-btn"
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
