import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getAgentTrace } from '../api/observability'
import { extractErrorMessage } from '../api/client'
import './agent-monitoring.css'

const STEP_ICONS = { completed: '✓', failed: '✕', skipped: '–' }

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

  if (loading) return <p className="dashboard-muted">Loading…</p>
  if (error) return <div className="alert-error">{error}</div>
  if (!trace) return null

  return (
    <div className="trace-viewer-page">
      <button className="chat-back" onClick={() => navigate('/agent-monitoring')} aria-label="Back to monitoring">
        ←
      </button>
      <h1>Request</h1>
      <p className="dashboard-subtitle trace-id">ID: {trace.request_id}</p>

      <div className="trace-summary-row">
        <span className={`trace-status-badge status-${trace.status}`}>{trace.status}</span>
        {trace.final_agent && <span className="trace-agent">{trace.final_agent}</span>}
        {trace.error_type && <span className="trace-error-type">{trace.error_type.replace(/_/g, ' ')}</span>}
      </div>

      <ul className="trace-step-list">
        {trace.steps.map((step) => (
          <li key={step.id} className="card trace-step-card">
            <div className="trace-step-header">
              <span className={`trace-step-icon status-${step.status}`}>{STEP_ICONS[step.status] || '…'}</span>
              <span className="trace-step-component">{step.component}</span>
              <span className="trace-step-action">{step.action}</span>
              <span className="trace-step-latency">{step.latency_ms != null ? `${step.latency_ms}ms` : ''}</span>
            </div>
            {Object.keys(step.metadata || {}).length > 0 && (
              <div className="trace-step-metadata">
                {Object.entries(step.metadata).map(([key, value]) => (
                  <span key={key} className="trace-metadata-chip">
                    {key}: {String(value)}
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>

      <div className="trace-total">
        Total: {trace.total_latency_ms != null ? `${(trace.total_latency_ms / 1000).toFixed(2)}s` : '—'}
      </div>
    </div>
  )
}
