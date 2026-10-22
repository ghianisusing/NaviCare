import { useEffect, useState } from 'react'
import { getMyProfile, updateMyProfile } from '../api/patients'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
import './profile.css'

export default function Profile() {
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState({ first_name: '', last_name: '', date_of_birth: '', phone_number: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const data = await getMyProfile()
        setProfile(data)
        setForm({
          first_name: data.first_name || '',
          last_name: data.last_name || '',
          date_of_birth: data.date_of_birth || '',
          phone_number: data.phone_number || '',
        })
      } catch (err) {
        setError(extractErrorMessage(err))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  function update(field) {
    return (event) => {
      setSaved(false)
      setForm((prev) => ({ ...prev, [field]: event.target.value }))
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const updated = await updateMyProfile(form)
      setProfile(updated)
      setSaved(true)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="page" aria-label="Loading your record">
        <div className="skeleton" style={{ height: 96 }} />
        <div className="skeleton" style={{ height: 380 }} />
      </div>
    )
  }

  const fullName = [profile?.first_name, profile?.last_name].filter(Boolean).join(' ') || 'Your record'
  const initials =
    [profile?.first_name, profile?.last_name]
      .filter(Boolean)
      .map((part) => part[0])
      .join('')
      .toUpperCase() || 'PT'

  return (
    <div className="page profile-page">
      <header className="page-header">
        <div>
          <h1 className="page-title">My record</h1>
          <p className="page-subtitle">Keep your details up to date so your care team can reach you.</p>
        </div>
      </header>

      {error && (
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      )}
      {saved && (
        <div className="alert-success" role="status">
          <Icon name="check" size={16} strokeWidth={2.4} />
          Your details were saved.
        </div>
      )}

      <section className="profile-identity">
        <span className="profile-avatar" aria-hidden="true">{initials}</span>
        <div className="profile-identity-text">
          <span className="profile-name">{fullName}</span>
          <span className="profile-email">{profile?.email}</span>
        </div>
        <span className="badge badge-success badge-dot">Active</span>
      </section>

      <div className="profile-grid">
        <form onSubmit={handleSubmit} className="card profile-card">
          <div className="profile-card-header">
            <h2 className="section-title">Personal details</h2>
            <p className="muted">Used by your navigator and appointment coordinators.</p>
          </div>

          <div className="profile-card-body">
            <div className="profile-row">
              <div className="field">
                <label htmlFor="first_name">First name</label>
                <input id="first_name" type="text" value={form.first_name} onChange={update('first_name')} required />
              </div>
              <div className="field">
                <label htmlFor="last_name">Last name</label>
                <input id="last_name" type="text" value={form.last_name} onChange={update('last_name')} required />
              </div>
            </div>

            <div className="profile-row">
              <div className="field">
                <label htmlFor="date_of_birth">Date of birth</label>
                <input id="date_of_birth" type="date" value={form.date_of_birth} onChange={update('date_of_birth')} />
              </div>
              <div className="field">
                <label htmlFor="phone_number">Phone</label>
                <input
                  id="phone_number"
                  type="tel"
                  autoComplete="tel"
                  placeholder="(555) 000-0000"
                  value={form.phone_number}
                  onChange={update('phone_number')}
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="account_email">Email</label>
              <input id="account_email" type="email" value={profile?.email || ''} disabled />
              <span className="field-hint">Contact your clinic to change the email on your account.</span>
            </div>
          </div>

          <div className="profile-card-footer">
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>

        <aside className="profile-aside">
          <div className="info-card">
            <span className="info-card-icon">
              <Icon name="lock" size={17} />
            </span>
            <h3>Your privacy</h3>
            <p>
              Your record and conversations are tied to your account. Other patients can never see them, and only your
              care team can access them.
            </p>
          </div>

          <div className="info-card">
            <span className="info-card-icon">
              <Icon name="headset" size={17} />
            </span>
            <h3>Need a hand?</h3>
            <p>
              Ask the Navigator to connect you with a person from Care Support, or contact your clinic reception.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
