import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { homePathFor, isStaffUser } from '../auth/roles'

/**
 * Client-side gating for role-specific routes. This is a UX convenience
 * only — the real enforcement is server-side via core/permissions.py
 * (IsCareCoordinator / IsSystemAdmin), which rejects the API calls these
 * pages make regardless of what the frontend renders.
 *
 * Anyone sent away from a route lands on their own home page.
 */

/** Patient-only pages (dashboard, chat, care plan…). Staff go to their workspace. */
export function PatientRoute() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (isStaffUser(user)) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}

/** Care coordinator (is_staff) pages. */
export function StaffRoute() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user?.is_staff) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}

/** System admin (is_superuser) pages. */
export function AdminRoute() {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user?.is_superuser) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}

/** Sends "/" and unknown URLs to the signed-in user's home page. */
export function HomeRedirect() {
  const { user, loading } = useAuth()

  if (loading) return null
  return <Navigate to={user ? homePathFor(user) : '/login'} replace />
}
