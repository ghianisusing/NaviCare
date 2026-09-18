import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAgentMetrics, listAgentTraces } from '../api/observability'
import { extractErrorMessage } from '../api/client'
import './agent-monitoring.css'

export default function AgentMonitoring() {
  const [metrics, setMetrics] = useState(null)
  const [traces, setTraces] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')
      try {
        const [metricsData, tracesData] = await Promise.all([getAgentMetrics(), listAgentTraces()])
        if (!cancelled) {
          setMetrics(metricsData)
          setTraces(tracesData)
        }
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
  }, [])

  if (loading) return <p className="dashboard-muted">Loading…</p>
  if (error) return <div className="alert-error">{error}</div>
  if (!metrics) return null

  const successRate =
    metrics.agent_executions > 0
      ? `${((metrics.successful_executions / metrics.agent_executions) * 100).toFixed(1)}%`
      : '—'

  return (
    <div className="agent-monitoring-page">
      <h1>Agent Monitoring</h1>
      <p className="dashboard-subtitle">System-wide execution metrics, computed from stored agent traces.</p>

      <div className="metrics-grid">
        <div className="card metric-card">
          <span className="metric-value">{metrics.agent_executions}</span>
          <span className="metric-label">Requests</span>
        </div>
        <div className="card metric-card">
          <span className="metric-value">{successRate}</span>
          <span className="metric-label">Success Rate</span>
        </div>
        <div className="card metric-card">
          <span className="metric-value">{metrics.escalations}</span>
          <span className="metric-label">Escalations</span>
        </div>
        <div className="card metric-card">
          <span className="metric-value">{metrics.tool_calls}</span>
          <span className="metric-label">Tool Calls</span>
        </div>
        <div className="card metric-card">
          <span className="metric-value">{metrics.tool_failures}</span>
          <span className="metric-label">Tool Failures</span>
        </div>
        <div className="card metric-card">
          <span className="metric-value">{(metrics.avg_latency_ms / 1000).toFixed(2)}s</span>
          <span className="metric-label">Avg Latency</span>
        </div>
      </div>

      <section className="recent-section">
        <h2>Requests by agent</h2>
        {metrics.executions_by_agent.length === 0 ? (
          <p className="dashboard-muted">No executions recorded yet.</p>
        ) : (
          <ul className="breakdown-list">
            {metrics.executions_by_agent.map((row) => (
              <li key={row.final_agent}>
                <span className="breakdown-label">{row.final_agent}</span>
                <span className="breakdown-value">{row.count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {metrics.failures_by_error_type.length > 0 && (
        <section className="recent-section">
          <h2>Failures by error type</h2>
          <ul className="breakdown-list">
            {metrics.failures_by_error_type.map((row) => (
              <li key={row.error_type}>
                <span className="breakdown-label">{row.error_type.replace(/_/g, ' ')}</span>
                <span className="breakdown-value">{row.count}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="recent-section">
        <h2>Recent traces</h2>
        {traces.length === 0 ? (
          <p className="dashboard-muted">No traces recorded yet.</p>
        ) : (
          <ul className="trace-list">
            {traces.map((trace) => (
              <li key={trace.id} className="card trace-row">
                <div>
                  <span className={`trace-status-badge status-${trace.status}`}>{trace.status}</span>
                  <span className="trace-agent">{trace.final_agent || '—'}</span>
                  <span className="trace-time">
                    {trace.total_latency_ms != null ? `${trace.total_latency_ms}ms` : ''}
                  </span>
                </div>
                <Link className="btn btn-secondary" to={`/agent-monitoring/traces/${trace.id}`}>
                  View
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
