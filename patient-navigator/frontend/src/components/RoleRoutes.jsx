import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

/**
 * Client-side gating for staff-only routes. This is a UX convenience
 * only — the real enforcement is server-side via
 * core/permissions.py's IsCareCoordinator, which rejects the API calls
 * these pages make regardless of what the frontend renders.
 */
export function StaffRoute() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user?.is_staff) return <Navigate to="/dashboard" replace />
  return <Outlet />
}

/** Same, for superuser-only observability routes (IsSystemAdmin). */
export function AdminRoute() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user?.is_superuser) return <Navigate to="/dashboard" replace />
  return <Outlet />
}
