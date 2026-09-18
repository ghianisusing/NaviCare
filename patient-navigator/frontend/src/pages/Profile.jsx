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

  if (loading) return <p className="dashboard-muted">Retrieving patient record…</p>

  return (
    <div className="profile-page">
      <div className="profile-header-group">
        <h1>Patient Medical Record & Profile</h1>
        <p className="dashboard-subtitle">
          Manage your verified demographic data, primary contact details, and portal security settings.
        </p>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {saved && <div className="alert-success">✓ Patient record updated successfully.</div>}

      <div className="profile-grid">
        <div className="card profile-card">
          <div className="card-section-header">
            <h3>Demographics & Contact Information</h3>
            <p className="dashboard-muted">Used by clinical navigators and appointment coordinators.</p>
          </div>

          <form onSubmit={handleSubmit} className="profile-form">
            <div className="profile-row">
              <div className="field">
                <label htmlFor="first_name">Legal First Name</label>
                <input
                  id="first_name"
                  type="text"
                  value={form.first_name}
                  onChange={update('first_name')}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="last_name">Legal Last Name</label>
                <input
                  id="last_name"
                  type="text"
                  value={form.last_name}
                  onChange={update('last_name')}
                  required
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="date_of_birth">Date of Birth</label>
              <input
                id="date_of_birth"
                type="date"
                value={form.date_of_birth}
                onChange={update('date_of_birth')}
              />
            </div>

            <div className="field">
              <label htmlFor="phone_number">Primary Contact Phone</label>
              <input
                id="phone_number"
                type="tel"
                placeholder="(555) 000-0000"
                value={form.phone_number}
                onChange={update('phone_number')}
              />
            </div>

            <div className="field">
              <label>Portal Account Email</label>
              <input type="email" value={profile?.email || ''} disabled />
              <span className="field-hint">Primary email cannot be changed directly in self-service.</span>
            </div>

            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? 'Saving changes…' : 'Save Patient Profile'}
            </button>
          </form>
        </div>

        <aside className="profile-security-aside">
          <div className="card security-card">
            <h4>Patient Data & Privacy Protection</h4>
            <p className="dashboard-muted">
              Your health data and care consultations are strictly isolated to your verified account. Neither other patients nor unapproved third parties can access your records.
            </p>
            <div className="security-badges">
              <span className="badge badge-success">✓ HIPAA Isolation Compliant</span>
              <span className="badge badge-primary">✓ Strict Identity Verification</span>
            </div>
          </div>

          <div className="card help-card">
            <h4>Need Clinical Support?</h4>
            <p className="dashboard-muted">
              If you have urgent medical questions or need assistance adjusting your record, contact your care navigator or clinic reception.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

