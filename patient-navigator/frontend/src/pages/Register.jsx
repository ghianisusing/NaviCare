import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'
import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'

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

  const passwordLength = form.password.length

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Manage appointments, follow-ups and get guidance from your Patient Navigator."
      footer={
        <>
          Already have an account? <Link to="/login">Sign in</Link>
        </>
      }
    >
      {error && (
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="auth-form">
        <div className="auth-row">
          <div className="field">
            <label htmlFor="firstName">First name</label>
            <input id="firstName" type="text" autoComplete="given-name" value={form.firstName} onChange={update('firstName')} required />
          </div>
          <div className="field">
            <label htmlFor="lastName">Last name</label>
            <input id="lastName" type="text" autoComplete="family-name" value={form.lastName} onChange={update('lastName')} required />
          </div>
        </div>
        <div className="field">
          <label htmlFor="username">Username</label>
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
          <label htmlFor="email">Email</label>
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
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={update('password')}
            minLength={10}
            aria-describedby="password-hint"
            required
          />
          <span id="password-hint" className={`field-hint ${passwordLength >= 10 ? 'field-hint-ok' : ''}`}>
            {passwordLength >= 10 ? (
              <>
                <Icon name="check" size={13} strokeWidth={2.4} /> Looks good
              </>
            ) : (
              'At least 10 characters'
            )}
          </span>
        </div>
        <button className="btn btn-primary btn-lg btn-block" type="submit" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  )
}
