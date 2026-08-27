import axios from 'axios'

// Backend base URL. In production this should be set via a Vite env var
// (VITE_API_BASE_URL) rather than hardcoded, so the frontend build never
// needs to embed environment-specific secrets or hosts.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const ACCESS_KEY = 'pn_access_token'
const REFRESH_KEY = 'pn_refresh_token'

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const client = axios.create({ baseURL: BASE_URL })

client.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Friendly, generic error message extraction — the backend already
// collapses raw exceptions into { error: "..." }, this just makes sure
// every call site can rely on that shape even for network failures.
export function extractErrorMessage(error) {
  if (error.response?.data?.error) return error.response.data.error
  if (error.response?.data?.details) {
    const details = error.response.data.details
    const firstKey = Object.keys(details)[0]
    if (firstKey) return Array.isArray(details[firstKey]) ? details[firstKey][0] : String(details[firstKey])
  }
  return 'Something went wrong. Please try again.'
}

let refreshPromise = null

async function refreshAccessToken() {
  const refresh = tokenStorage.getRefresh()
  if (!refresh) throw new Error('No refresh token available')

  const response = await axios.post(`${BASE_URL}/auth/token/refresh/`, { refresh })
  tokenStorage.set(response.data.access, response.data.refresh)
  return response.data.access
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthEndpoint = original?.url?.includes('/auth/login') || original?.url?.includes('/auth/register')

    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const newAccess = await refreshPromise
        refreshPromise = null
        original.headers.Authorization = `Bearer ${newAccess}`
        return client(original)
      } catch (refreshError) {
        refreshPromise = null
        tokenStorage.clear()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default client
