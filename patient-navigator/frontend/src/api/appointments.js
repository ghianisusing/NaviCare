import client from './client'

export async function listAppointments(status) {
  const { data } = await client.get('/appointments/', { params: status ? { status } : {} })
  return data
}

export async function cancelAppointment(id) {
  await client.delete(`/appointments/${id}/`)
}

export async function rescheduleAppointment(id, { start_time, end_time }) {
  const { data } = await client.patch(`/appointments/${id}/`, { start_time, end_time })
  return data
}

export async function confirmAgentAction(actionId) {
  const { data } = await client.post(`/appointments/agent-actions/${actionId}/confirm/`)
  return data
}

export async function declineAgentAction(actionId) {
  const { data } = await client.post(`/appointments/agent-actions/${actionId}/decline/`)
  return data
}
