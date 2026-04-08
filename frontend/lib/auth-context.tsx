"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

import * as api from "./api"
import { clearToken, getToken, setToken } from "./auth"

interface AuthUser {
  id: string
  email: string
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setTimeout(() => setLoading(false), 0)
      return
    }
    api.getMe()
      .then((u) => setUser(u))
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const { access_token } = await api.login(email, password)
    setToken(access_token)
    setUser(await api.getMe())
  }

  async function register(email: string, password: string) {
    const { access_token } = await api.register(email, password)
    setToken(access_token)
    setUser(await api.getMe())
  }

  function logout() {
    clearToken()
    setUser(null)
    if (typeof window !== "undefined") window.location.href = "/login"
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
