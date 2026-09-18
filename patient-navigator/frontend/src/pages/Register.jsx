import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'
import './auth.css'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    username: '',
    email: '',
    password: '',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function update(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await register(form)
      navigate('/dashboard', { replace: true })
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

        <h1>Create Patient Account</h1>
        <p className="auth-subtitle">Register to manage appointments, care follow-ups, and receive guidance.</p>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="auth-row">
            <div className="field">
              <label htmlFor="firstName">Legal First Name</label>
              <input id="firstName" type="text" value={form.firstName} onChange={update('firstName')} required />
            </div>
            <div className="field">
              <label htmlFor="lastName">Legal Last Name</label>
              <input id="lastName" type="text" value={form.lastName} onChange={update('lastName')} required />
            </div>
          </div>
          <div className="field">
            <label htmlFor="username">Preferred Username</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={form.username}
              onChange={update('username')}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="name@example.com"
              value={form.email}
              onChange={update('email')}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password (Minimum 10 characters)</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              value={form.password}
              onChange={update('password')}
              minLength={10}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? 'Creating Patient Record…' : 'Register Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already registered? <Link to="/login">Sign in to your record</Link>
        </div>

        <div className="auth-security-notice">
          <span aria-hidden="true">🔒</span>
          <span>Your personal medical records are isolated and protected under strict healthcare privacy controls.</span>
        </div>
      </div>
    </div>
  )
}

