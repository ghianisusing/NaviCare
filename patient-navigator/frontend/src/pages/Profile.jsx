import { useEffect, useState } from 'react'
import { getMyProfile, updateMyProfile } from '../api/patients'
import { extractErrorMessage } from '../api/client'
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

  if (loading) return <p className="dashboard-muted">Loading profile…</p>

  return (
    <div className="profile-page">
      <h1>Your profile</h1>
      <p className="dashboard-subtitle">Keep your details up to date so we can support you better.</p>

      {error && <div className="alert-error">{error}</div>}
      {saved && <div className="alert-success">Profile updated.</div>}

      <div className="card profile-card">
        <form onSubmit={handleSubmit}>
          <div className="auth-row">
            <div className="field">
              <label htmlFor="first_name">First name</label>
              <input id="first_name" type="text" value={form.first_name} onChange={update('first_name')} required />
            </div>
            <div className="field">
              <label htmlFor="last_name">Last name</label>
              <input id="last_name" type="text" value={form.last_name} onChange={update('last_name')} required />
            </div>
          </div>
          <div className="field">
            <label htmlFor="date_of_birth">Date of birth</label>
            <input id="date_of_birth" type="date" value={form.date_of_birth} onChange={update('date_of_birth')} />
          </div>
          <div className="field">
            <label htmlFor="phone_number">Phone number</label>
            <input id="phone_number" type="tel" value={form.phone_number} onChange={update('phone_number')} />
          </div>
          <div className="field">
            <label>Email</label>
            <input type="email" value={profile?.email || ''} disabled />
          </div>
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </div>
    </div>
  )
}
