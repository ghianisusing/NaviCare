import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { homePathFor } from '../auth/roles'

// Keeps already-authenticated users off Login/Register.
export default function GuestRoute() {
  const { user, isAuthenticated, loading } = useAuth()

  if (loading) return null
  if (isAuthenticated) return <Navigate to={homePathFor(user)} replace />
  return <Outlet />
}
