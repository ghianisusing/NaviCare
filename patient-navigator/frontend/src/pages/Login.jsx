import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'
import './auth.css'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login({ username, password })
      const destination = location.state?.from?.pathname || '/dashboard'
      navigate(destination, { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="auth-brand">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
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
          <div className="auth-brand-text">
            <span>NaviCare</span>
            <span className="auth-brand-sub">Patient & Care Portal</span>
          </div>
        </div>

        <h1>Sign In to Your Record</h1>
        <p className="auth-subtitle">Secure access to your appointments, care plans, and navigator consultations.</p>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="username">Username or Patient ID</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? 'Authenticating…' : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          New to NaviCare? <Link to="/register">Create a patient account</Link>
        </div>

        <div className="auth-security-notice">
          <span aria-hidden="true">🔒</span>
          <span>Protected by strict patient data isolation and encrypted access standards.</span>
        </div>
      </div>
    </div>
  )
}

