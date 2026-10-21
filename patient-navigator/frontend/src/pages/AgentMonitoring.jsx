import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAgentMetrics, listAgentTraces } from '../api/observability'
import { extractErrorMessage } from '../api/client'
import Icon from '../components/Icon'
import './agent-monitoring.css'

function Breakdown({ rows, labelKey, emptyText, tone }) {
  if (rows.length === 0) return <p className="muted">{emptyText}</p>
  const max = Math.max(...rows.map((row) => row.count), 1)
  return (
    <ul className="breakdown-list">
      {rows.map((row) => (
        <li key={row[labelKey]}>
          <div className="breakdown-row">
            <span className="breakdown-label">{String(row[labelKey]).replace(/_/g, ' ')}</span>
            <span className="breakdown-value">{row.count}</span>
          </div>
          <div className="breakdown-track" aria-hidden="true">
            <div className={`breakdown-fill ${tone}`} style={{ width: `${(row.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

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

  const header = (
    <header className="page-header">
      <div>
        <h1 className="page-title">System health</h1>
        <p className="page-subtitle">Agent execution metrics, computed from stored traces.</p>
      </div>
    </header>
  )

  if (loading) {
    return (
      <div className="page">
        {header}
        <div className="stat-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 82 }} />
          ))}
        </div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        {header}
        <div className="alert-error" role="alert">
          <Icon name="info" size={16} />
          {error}
        </div>
      </div>
    )
  }
  if (!metrics) return null

  const successRate =
    metrics.agent_executions > 0
      ? `${((metrics.successful_executions / metrics.agent_executions) * 100).toFixed(1)}%`
      : '—'

  const tiles = [
    { label: 'Requests', value: metrics.agent_executions },
    { label: 'Success rate', value: successRate },
    { label: 'Escalations', value: metrics.escalations },
    { label: 'Tool calls', value: metrics.tool_calls },
    { label: 'Tool failures', value: metrics.tool_failures, alert: metrics.tool_failures > 0 },
    { label: 'Avg latency', value: `${(metrics.avg_latency_ms / 1000).toFixed(2)}s` },
  ]

  return (
    <div className="page agent-monitoring-page">
      {header}

      <section className="stat-grid metrics-grid" aria-label="Key metrics">
        {tiles.map((tile) => (
          <div key={tile.label} className="stat-tile">
            <span className="stat-label">{tile.label}</span>
            <span className={`stat-value ${tile.alert ? 'is-alert' : ''}`}>{tile.value}</span>
          </div>
        ))}
      </section>

      <div className="monitoring-grid">
        <section className="card monitoring-card">
          <h2 className="section-title">Requests by agent</h2>
          <Breakdown
            rows={metrics.executions_by_agent}
            labelKey="final_agent"
            emptyText="No executions recorded yet."
            tone="primary"
          />
        </section>

        <section className="card monitoring-card">
          <h2 className="section-title">Failures by error type</h2>
          <Breakdown
            rows={metrics.failures_by_error_type}
            labelKey="error_type"
            emptyText="No failures recorded."
            tone="danger"
          />
        </section>
      </div>

      <section>
        <div className="section-header">
          <h2 className="section-title">Recent traces</h2>
        </div>
        {traces.length === 0 ? (
          <div className="empty-state compact">
            <div className="empty-icon">
              <Icon name="layers" size={20} />
            </div>
            <h3>No traces yet</h3>
            <p>Traces appear here as patients talk to the Navigator.</p>
          </div>
        ) : (
          <ul className="list-group">
            {traces.map((trace) => (
              <li key={trace.id}>
                <Link className="trace-row" to={`/agent-monitoring/traces/${trace.id}`}>
                  <span className={`trace-status status-${trace.status}`}>{trace.status}</span>
                  <span className="trace-agent">{trace.final_agent || '—'}</span>
                  <span className="trace-latency">
                    {trace.total_latency_ms != null ? `${trace.total_latency_ms} ms` : ''}
                  </span>
                  <Icon name="chevronRight" size={16} className="row-chevron" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
