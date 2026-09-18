import client from './client'

export async function listEscalations(params = {}) {
  const { data } = await client.get('/escalations/', { params })
  return data
}

export async function getEscalation(id) {
  const { data } = await client.get(`/escalations/${id}/`)
  return data
}

export async function assignEscalation(id) {
  const { data } = await client.post(`/escalations/${id}/assign/`)
  return data
}

export async function resolveEscalation(id) {
  const { data } = await client.post(`/escalations/${id}/resolve/`)
  return data
}

export async function respondToEscalation(id, content) {
  const { data } = await client.post(`/escalations/${id}/respond/`, { content })
  return data
}
