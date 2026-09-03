import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listNotifications } from '../api/notifications'
import './app-shell.css'

export default function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function loadUnread() {
      try {
        const data = await listNotifications(true)
        if (!cancelled) setUnreadCount(data.length)
      } catch {
        // Non-critical — a failed badge fetch shouldn't disrupt navigation.
      }
    }
    loadUnread()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-header-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 2 L12 22 M4 12 L20 12"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  opacity="0.35"
                />
                <circle cx="12" cy="12" r="3.2" fill="currentColor" />
              </svg>
            </span>
            NaviCare
          </div>
          <nav className="shell-nav">
            <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active' : '')}>
              Dashboard
            </NavLink>
            <NavLink to="/follow-ups" className={({ isActive }) => (isActive ? 'active' : '')}>
              Follow-ups
            </NavLink>
            <NavLink to="/notifications" className={({ isActive }) => (isActive ? 'active' : '')}>
              Notifications
              {unreadCount > 0 && <span className="shell-notification-badge">{unreadCount}</span>}
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => (isActive ? 'active' : '')}>
              Profile
            </NavLink>
          </nav>
          <div className="shell-user">
            {user && <span className="shell-username">{user.username}</span>}
            <button className="btn btn-secondary" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
    </div>
  )
}
