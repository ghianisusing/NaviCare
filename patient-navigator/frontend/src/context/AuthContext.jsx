import { createContext, useContext, useEffect, useState } from 'react'
import * as authApi from '../api/auth'
import { tokenStorage } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function hydrate() {
      if (!tokenStorage.getAccess()) {
        setLoading(false)
        return
      }
      try {
        const current = await authApi.getCurrentUser()
        setUser(current)
      } catch {
        tokenStorage.clear()
      } finally {
        setLoading(false)
      }
    }
    hydrate()
  }, [])

  async function login(credentials) {
    const loggedInUser = await authApi.login(credentials)
    setUser(loggedInUser)
    return loggedInUser
  }

  async function register(payload) {
    const newUser = await authApi.register(payload)
    setUser(newUser)
    return newUser
  }

  async function logout() {
    await authApi.logout()
    setUser(null)
  }

  const value = { user, loading, isAuthenticated: Boolean(user), login, register, logout }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
