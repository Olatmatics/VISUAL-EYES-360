import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, clearTokens, storeTokens } from '../api/client'
import type { LoginResponse, UserContext } from '../types'

interface AuthState {
  user: UserContext | null
  loading: boolean
  login: (userId: string, password: string) => Promise<LoginResponse>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  can: (module: string, action: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserContext | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    try {
      const me = await api.get<UserContext>('/auth/me')
      setUser(me)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (localStorage.getItem('ve_access_token')) {
      void loadUser()
    } else {
      setLoading(false)
    }
  }, [loadUser])

  const login = useCallback(async (userId: string, password: string) => {
    const data = await api.post<LoginResponse>('/auth/login', { user_id: userId, password })
    storeTokens(data)
    setUser(data.user)
    return data
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      /* ignore */
    }
    clearTokens()
    setUser(null)
  }, [])

  const can = useCallback(
    (module: string, action: string) => {
      if (!user) return false
      if (user.is_super_admin) return true
      return user.permissions.includes(`${module}:${action}`)
    },
    [user],
  )

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser: loadUser, can }),
    [user, loading, login, logout, loadUser, can],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
