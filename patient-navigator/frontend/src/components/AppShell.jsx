import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listNotifications } from '../api/notifications'
import './app-shell.css'

export default function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [unreadCount, setUnreadCount] = useState(0)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
    window.addEventListener('notifications:updated', loadUnread)
    return () => {
      cancelled = true
      window.removeEventListener('notifications:updated', loadUnread)
    }
  }, [location.pathname])



  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  const userInitials = user?.username
    ? user.username.slice(0, 2).toUpperCase()
    : 'PT'

  return (
    <div className="shell">
      {/* Top Clinical Safety / Emergency Banner */}
      <div className="shell-emergency-bar">
        <div className="shell-emergency-inner">
          <span className="emergency-icon" aria-hidden="true">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </span>
          <span className="emergency-text">
            <strong>Medical Emergency:</strong> For severe chest pain, trouble breathing, or other life-threatening symptoms, contact your local emergency service or go to the nearest emergency department.
          </span>
        </div>
      </div>

      <header className="shell-header">
        <div className="shell-header-inner">
          <NavLink to="/dashboard" className="brand" aria-label="NaviCare Home">
            <span className="brand-mark" aria-hidden="true">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 2 L20 5.5 V11 C20 16.5 16.5 20.5 12 22 C7.5 20.5 4 16.5 4 11 V5.5 L12 2Z"
                  fill="var(--color-primary-tint)"
                  stroke="var(--color-primary)"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
                <path
                  d="M12 7 V15 M8 11 H16"
                  stroke="var(--color-primary)"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <div className="brand-text-group">
              <span className="brand-title">NaviCare</span>
              <span className="brand-badge">Patient Portal</span>
            </div>
          </NavLink>

          <button
            className="shell-menu-toggle"
            type="button"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
            aria-controls="primary-navigation"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              {mobileMenuOpen ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>

          <nav
            id="primary-navigation"
            className={`shell-nav ${mobileMenuOpen ? 'open' : ''}`}
            onClick={() => setMobileMenuOpen(false)}
          >
            <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active' : '')}>
              Dashboard
            </NavLink>
            <NavLink to="/follow-ups" className={({ isActive }) => (isActive ? 'active' : '')}>
              Care Plan & Tasks
            </NavLink>
            <NavLink to="/notifications" className={({ isActive }) => (isActive ? 'active' : '')}>
              Notifications
              {unreadCount > 0 && <span className="shell-notification-badge">{unreadCount}</span>}
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => (isActive ? 'active' : '')}>
              My Record
            </NavLink>
            {user?.is_staff && (
              <NavLink to="/care-support" className={({ isActive }) => (isActive ? 'active' : '')}>
                Care Support
              </NavLink>
            )}
            {user?.is_superuser && (
              <NavLink to="/agent-monitoring" className={({ isActive }) => (isActive ? 'active' : '')}>
                System Health
              </NavLink>
            )}
          </nav>

          <div className="shell-user">
            {user && (
              <div className="shell-patient-profile">
                <span className="shell-avatar" aria-hidden="true">
                  {userInitials}
                </span>
                <div className="shell-user-meta">
                  <span className="shell-username">{user.username}</span>
                  {user.is_staff && <span className="shell-role-tag">Care Staff</span>}
                </div>
              </div>
            )}
            <button className="btn btn-secondary btn-sm shell-logout-btn" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="shell-main">
        <Outlet />
      </main>

      <footer className="shell-footer">
        <div className="shell-footer-inner">
          <div className="shell-footer-brand">
            <strong>NaviCare Patient Care Portal</strong>
            <span>Secure, source-attributed clinical care navigation and appointment scheduling.</span>
          </div>
          <div className="shell-footer-links">
            <span>HIPAA-aligned Patient Privacy</span>
            <span>•</span>
            <span>Care Navigation v2.0</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
