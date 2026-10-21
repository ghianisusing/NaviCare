import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { listNotifications } from '../api/notifications'
import { createConversation } from '../api/conversations'
import Icon, { BrandMark } from './Icon'
import './app-shell.css'

function NavItem({ to, icon, children, badge }) {
  return (
    <NavLink to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
      <Icon name={icon} size={18} />
      <span className="nav-item-label">{children}</span>
      {badge > 0 && <span className="nav-badge">{badge > 99 ? '99+' : badge}</span>}
    </NavLink>
  )
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [unreadCount, setUnreadCount] = useState(0)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [startingChat, setStartingChat] = useState(false)

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

  // Close the mobile drawer whenever the route changes.
  const [drawerPath, setDrawerPath] = useState(location.pathname)
  if (drawerPath !== location.pathname) {
    setDrawerPath(location.pathname)
    setDrawerOpen(false)
  }

  useEffect(() => {
    if (!drawerOpen) return undefined
    function handleKeyDown(event) {
      if (event.key === 'Escape') setDrawerOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [drawerOpen])

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  async function handleNewChat() {
    setStartingChat(true)
    try {
      const conversation = await createConversation()
      navigate(`/chat/${conversation.id}`)
    } catch {
      navigate('/dashboard')
    } finally {
      setStartingChat(false)
    }
  }

  const userInitials = user?.username ? user.username.slice(0, 2).toUpperCase() : 'PT'
  const roleLabel = user?.is_superuser ? 'Administrator' : user?.is_staff ? 'Care staff' : 'Patient'
  const isChat = location.pathname.startsWith('/chat/')

  return (
    <div className={`shell ${drawerOpen ? 'drawer-open' : ''}`}>
      <aside className="sidebar" id="primary-navigation" aria-label="Primary">
        <div className="sidebar-top">
          <NavLink to="/dashboard" className="brand" aria-label="NaviCare home">
            <BrandMark size={30} />
            <span className="brand-title">NaviCare</span>
          </NavLink>
          <button
            type="button"
            className="icon-btn sidebar-close"
            onClick={() => setDrawerOpen(false)}
            aria-label="Close menu"
          >
            <Icon name="x" />
          </button>
        </div>

        <button type="button" className="sidebar-cta" onClick={handleNewChat} disabled={startingChat}>
          <span className="sidebar-cta-icon">
            <Icon name="sparkle" size={16} />
          </span>
          {startingChat ? 'Starting…' : 'Ask the Navigator'}
        </button>

        <nav className="sidebar-nav">
          <NavItem to="/dashboard" icon="home">Home</NavItem>
          <NavItem to="/follow-ups" icon="tasks">Care plan</NavItem>
          <NavItem to="/notifications" icon="bell" badge={unreadCount}>Notifications</NavItem>
          <NavItem to="/profile" icon="user">My record</NavItem>

          {(user?.is_staff || user?.is_superuser) && (
            <>
              <div className="sidebar-section-label">Workspace</div>
              {user?.is_staff && <NavItem to="/care-support" icon="headset">Care support</NavItem>}
              {user?.is_superuser && <NavItem to="/agent-monitoring" icon="activity">System health</NavItem>}
            </>
          )}
        </nav>

        <div className="sidebar-bottom">
          <div className="emergency-card" role="note">
            <div className="emergency-card-title">
              <Icon name="alert" size={15} strokeWidth={2} />
              Medical emergency?
            </div>
            <p>
              For chest pain, trouble breathing or other life-threatening symptoms, call your local emergency number or
              go to the nearest emergency department.
            </p>
          </div>

          {user && (
            <div className="sidebar-user">
              <span className="avatar" aria-hidden="true">{userInitials}</span>
              <div className="sidebar-user-meta">
                <span className="sidebar-username">{user.username}</span>
                <span className="sidebar-role">{roleLabel}</span>
              </div>
              <button type="button" className="icon-btn" onClick={handleLogout} aria-label="Sign out" title="Sign out">
                <Icon name="logout" size={17} />
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="drawer-scrim" onClick={() => setDrawerOpen(false)} aria-hidden="true" />

      <div className="shell-content">
        <header className="topbar">
          <button
            type="button"
            className="icon-btn"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            aria-expanded={drawerOpen}
            aria-controls="primary-navigation"
          >
            <Icon name="menu" size={20} />
            {unreadCount > 0 && <span className="topbar-dot" aria-hidden="true" />}
          </button>
          <NavLink to="/dashboard" className="brand" aria-label="NaviCare home">
            <BrandMark size={26} />
            <span className="brand-title">NaviCare</span>
          </NavLink>
          <button
            type="button"
            className="icon-btn topbar-ai"
            onClick={handleNewChat}
            disabled={startingChat}
            aria-label="Ask the Navigator"
          >
            <Icon name="sparkle" size={18} />
          </button>
        </header>
        <div className="topbar-emergency" role="note">
          <Icon name="alert" size={13} strokeWidth={2.2} />
          <span>Emergency? Call your local emergency number now.</span>
        </div>

        <main className={`shell-main ${isChat ? 'shell-main--flush' : ''}`}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
