import client, { tokenStorage } from './client'

export async function register({ username, email, password, firstName, lastName }) {
  const { data } = await client.post('/auth/register/', {
    username,
    email,
    password,
    first_name: firstName,
    last_name: lastName,
  })
  tokenStorage.set(data.access, data.refresh)
  return data.user
}

export async function login({ username, password }) {
  const { data } = await client.post('/auth/login/', { username, password })
  tokenStorage.set(data.access, data.refresh)
  return data.user
}

export async function logout() {
  const refresh = tokenStorage.getRefresh()
  try {
    if (refresh) await client.post('/auth/logout/', { refresh })
  } finally {
    tokenStorage.clear()
  }
}

export async function getCurrentUser() {
  const { data } = await client.get('/auth/me/')
  return data
}
