import client from './client'

export async function getAgentMetrics() {
  const { data } = await client.get('/agent-metrics/')
  return data
}

export async function listAgentTraces(params = {}) {
  const { data } = await client.get('/agent-traces/', { params })
  return data
}

export async function getAgentTrace(id) {
  const { data } = await client.get(`/agent-traces/${id}/`)
  return data
}
