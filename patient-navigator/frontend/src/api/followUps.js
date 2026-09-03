import client from './client'

export async function listFollowUps(status) {
  const { data } = await client.get('/follow-ups/', { params: status ? { status } : {} })
  return data
}

export async function completeFollowUp(id) {
  const { data } = await client.patch(`/follow-ups/${id}/`, { status: 'completed' })
  return data
}

export async function cancelFollowUp(id) {
  await client.delete(`/follow-ups/${id}/`)
}

export async function listReminders(status) {
  const { data } = await client.get('/reminders/', { params: status ? { status } : {} })
  return data
}

export async function cancelReminder(id) {
  await client.delete(`/reminders/${id}/`)
}

export async function createAppointmentReminder(appointmentId, hoursBefore = 24) {
  const { data } = await client.post('/follow-ups/appointment-reminder/', {
    appointment: appointmentId,
    hours_before: hoursBefore,
  })
  return data
}
