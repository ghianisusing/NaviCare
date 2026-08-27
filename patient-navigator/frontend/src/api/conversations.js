import client from './client'

export async function listConversations() {
  const { data } = await client.get('/conversations/')
  return data
}

export async function createConversation(title = '') {
  const { data } = await client.post('/conversations/', { title })
  return data
}

export async function getConversation(id) {
  const { data } = await client.get(`/conversations/${id}/`)
  return data
}

export async function sendMessage(conversationId, content) {
  const { data } = await client.post(`/conversations/${conversationId}/messages/`, { content })
  return data
}
