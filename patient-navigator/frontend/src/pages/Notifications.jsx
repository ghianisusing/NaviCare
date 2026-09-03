import { useEffect, useState } from 'react'
import { listNotifications, markNotificationRead } from '../api/notifications'
import { extractErrorMessage } from '../api/client'
import './notifications.css'

function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export default function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    load()
  }, [])

  async function load() {
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
  }

  async function handleMarkRead(id) {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
    try {
      await markNotificationRead(id)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  return (
    <div className="notifications-page">
      <h1>Notifications</h1>
      <p className="dashboard-subtitle">Updates about your appointments and follow-ups.</p>

      {error && <div className="alert-error">{error}</div>}
      {loading && <p className="dashboard-muted">Loading…</p>}

      {!loading && notifications.length === 0 && (
        <div className="card empty-state">
          <p>No notifications yet.</p>
        </div>
      )}

      {!loading && notifications.length > 0 && (
        <ul className="notification-list">
          {notifications.map((notification) => (
            <li
              key={notification.id}
              className={`card notification-card ${notification.read ? 'notification-read' : ''}`}
              onClick={() => !notification.read && handleMarkRead(notification.id)}
            >
              <span className="notification-dot" aria-hidden="true" />
              <div>
                <div className="notification-title">{notification.title}</div>
                <div className="notification-message">{notification.message}</div>
                <div className="notification-time">{timeAgo(notification.created_at)}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
