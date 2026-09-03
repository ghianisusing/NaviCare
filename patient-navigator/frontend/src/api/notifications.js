import client from './client'

export async function listNotifications(unreadOnly = false) {
  const { data } = await client.get('/notifications/', { params: unreadOnly ? { unread: 1 } : {} })
  return data
}

export async function markNotificationRead(id) {
  const { data } = await client.patch(`/notifications/${id}/read/`)
  return data
}
