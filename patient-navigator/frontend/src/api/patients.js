import client from './client'

export async function getMyProfile() {
  const { data } = await client.get('/patients/me/')
  return data
}

export async function updateMyProfile(payload) {
  const { data } = await client.patch('/patients/me/', payload)
  return data
}
