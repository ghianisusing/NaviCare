import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import GuestRoute from './components/GuestRoute'
import { AdminRoute, StaffRoute } from './components/RoleRoutes'
import AppShell from './components/AppShell'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Profile from './pages/Profile'
import Chat from './pages/Chat'
import FollowUps from './pages/FollowUps'
import Notifications from './pages/Notifications'
import CareSupport from './pages/CareSupport'
import CareSupportDetail from './pages/CareSupportDetail'
import AgentMonitoring from './pages/AgentMonitoring'
import TraceViewer from './pages/TraceViewer'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<GuestRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/follow-ups" element={<FollowUps />} />
              <Route path="/notifications" element={<Notifications />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/chat/:conversationId" element={<Chat />} />

              {/* Care coordinator (is_staff) only */}
              <Route element={<StaffRoute />}>
                <Route path="/care-support" element={<CareSupport />} />
                <Route path="/care-support/:escalationId" element={<CareSupportDetail />} />
              </Route>

              {/* System admin (is_superuser) only */}
              <Route element={<AdminRoute />}>
                <Route path="/agent-monitoring" element={<AgentMonitoring />} />
                <Route path="/agent-monitoring/traces/:traceId" element={<TraceViewer />} />
              </Route>
            </Route>
          </Route>

          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
