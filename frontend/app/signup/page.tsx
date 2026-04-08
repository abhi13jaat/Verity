"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { useAuth } from "@/lib/auth-context"

export default function SignupPage() {
  const { register } = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    if (password !== confirm) {
      setError("Passwords do not match")
      return
    }
    setLoading(true)
    setError(null)
    try {
      await register(email.trim(), password)
      router.replace("/")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center px-4"
      style={{ background: "var(--background)", color: "var(--foreground)" }}>
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-2xl p-7 space-y-5"
        style={{ background: "var(--card)", border: "1px solid var(--border)" }}>

        <div className="flex flex-col items-center gap-3 mb-1">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-white text-lg font-bold"
            style={{ background: "linear-gradient(135deg, #4f8ef7 0%, #7c5df7 100%)" }}>V</div>
          <h1 className="text-xl font-semibold">Create your account</h1>
          <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>Your documents and chats stay private to you</p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus
            placeholder="you@example.com"
            className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none"
            style={{ background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)" }} />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required
            placeholder="At least 8 characters"
            className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none"
            style={{ background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)" }} />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Confirm password</label>
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required
            placeholder="••••••••"
            className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none"
            style={{ background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)" }} />
        </div>

        {error && (
          <div className="rounded-xl px-4 py-3 text-sm"
            style={{ background: "rgba(229,87,87,0.1)", border: "1px solid rgba(229,87,87,0.25)", color: "#e57373" }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={loading}
          className="w-full py-3 rounded-xl text-base font-semibold text-white"
          style={loading
            ? { background: "var(--secondary)", color: "var(--muted-foreground)", cursor: "not-allowed" }
            : { background: "linear-gradient(135deg, #4f8ef7 0%, #3a7aec 100%)" }}>
          {loading ? "Creating account…" : "Create account"}
        </button>

        <p className="text-sm text-center" style={{ color: "var(--muted-foreground)" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "#4f8ef7" }}>Sign in</Link>
        </p>
      </form>
    </div>
  )
}
