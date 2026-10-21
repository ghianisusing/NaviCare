import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getAgentTrace } from '../api/observability'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
import './agent-monitoring.css'

const STEP_ICONS = { completed: 'check', failed: 'x' }

export default function TraceViewer() {
  const { traceId } = useParams()
  const navigate = useNavigate()
  const [trace, setTrace] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getAgentTrace(traceId)
        if (!cancelled) setTrace(data)
      } catch (err) {
        if (!cancelled) setError(extractErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [traceId])

  const backLink = (
    <button className="back-link" onClick={() => navigate('/agent-monitoring')}>
      <Icon name="arrowLeft" size={16} /> System health
    </button>
  )

  if (loading) {
    return (
      <div className="page" aria-label="Loading trace">
        {backLink}
        <div className="skeleton" style={{ height: 64 }} />
        <div className="skeleton" style={{ height: 300 }} />
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        {backLink}
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      </div>
    )
  }
  if (!trace) return null

  return (
    <div className="page trace-viewer-page">
      {backLink}

      <header className="page-header">
        <div>
          <p className="page-eyebrow">Request trace</p>
          <h1 className="page-title trace-title">{trace.final_agent || 'Request'}</h1>
          <p className="trace-id">{trace.request_id}</p>
        </div>
        <div className="trace-summary">
          <span className={`trace-status status-${trace.status}`}>{trace.status}</span>
          {trace.error_type && <span className="badge badge-danger">{trace.error_type.replace(/_/g, ' ')}</span>}
          <span className="trace-total">
            <Icon name="clock" size={14} />
            {trace.total_latency_ms != null ? `${(trace.total_latency_ms / 1000).toFixed(2)}s total` : '—'}
          </span>
        </div>
      </header>

      <ol className="card trace-steps">
        {trace.steps.map((step) => (
          <li key={step.id} className="trace-step">
            <span className={`trace-step-icon status-${step.status}`} aria-label={step.status}>
              {STEP_ICONS[step.status] ? <Icon name={STEP_ICONS[step.status]} size={12} strokeWidth={2.8} /> : '–'}
            </span>
            <div className="trace-step-body">
              <div className="trace-step-header">
                <span className="trace-step-component">{step.component}</span>
                <span className="trace-step-action">{step.action}</span>
                <span className="trace-step-latency">{step.latency_ms != null ? `${step.latency_ms} ms` : ''}</span>
              </div>
              {Object.keys(step.metadata || {}).length > 0 && (
                <div className="trace-step-metadata">
                  {Object.entries(step.metadata).map(([key, value]) => (
                    <span key={key} className="trace-chip">
                      <span className="trace-chip-key">{key}</span>
                      {String(value)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
