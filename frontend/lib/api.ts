import { clearToken, getToken } from "./auth"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken()
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra }
}

function handleUnauthorized() {
  clearToken()
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = "/login"
  }
}

export interface QueryRequest {
  query: string
  domain?: string | null
  session_id?: string | null
  top_k?: number
}

export interface SourceItem {
  document_id: string
  chunk_index: number
  page_number: number | null
  score: number
  title: string | null
  text: string | null
}

export interface QueryResponse {
  answer: string
  chunks_used: number
  sources: SourceItem[]
}

export interface IngestRequest {
  source: string
  title: string
  domain?: string | null
}

export interface IngestResponse {
  document_id: string
  title: string
  status: string
}

export interface AsyncIngestResponse {
  task_id: string
  status: string
  message: string
}

export interface TaskStatusResponse {
  task_id: string
  status: string
  result?: Record<string, unknown>
  error?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(init?.headers) })
  if (res.status === 401) {
    handleUnauthorized()
    throw new Error("Unauthorized")
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text)
  }
  return res.json()
}

export function queryKB(req: QueryRequest): Promise<QueryResponse> {
  return request("/research/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}

export interface PipelineInfo {
  methods: string[]
  chunks_retrieved: number
  reranked: boolean
  has_hallucination: boolean
  grader_passed: boolean
}

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "sources"; sources: SourceItem[]; chunks_used: number }
  | { type: "pipeline"; methods: string[]; chunks_retrieved: number; reranked: boolean; has_hallucination: boolean; grader_passed: boolean }
  | { type: "error"; content: string }
  | { type: "done" }

export class RateLimitError extends Error {
  retryAfter: number
  constructor(retryAfter: number) {
    super("rate_limit")
    this.retryAfter = retryAfter
  }
}

export async function queryKBStream(
  req: QueryRequest,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  // Abort if the backend goes silent for too long, so the UI never hangs forever.
  const controller = new AbortController()
  const IDLE_MS = 90_000
  let idle = setTimeout(() => controller.abort(), IDLE_MS)
  const resetIdle = () => {
    clearTimeout(idle)
    idle = setTimeout(() => controller.abort(), IDLE_MS)
  }

  try {
    const res = await fetch(`${API_BASE}/research/query/stream`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(req),
      signal: controller.signal,
    })

    if (res.status === 401) {
      handleUnauthorized()
      throw new Error("Unauthorized")
    }

    if (res.status === 429) {
      const data = await res.json().catch(() => ({}))
      throw new RateLimitError(data?.detail?.retry_after ?? 1200)
    }

    if (!res.ok || !res.body) throw new Error(await res.text().catch(() => res.statusText))

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      resetIdle()

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() ?? ""

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6)) as StreamEvent
            onEvent(event)
          } catch { /* skip malformed lines */ }
        }
      }
    }
  } catch (err) {
    if (controller.signal.aborted) {
      throw new Error("The request timed out — the server stopped responding. Please try again.")
    }
    throw err
  } finally {
    clearTimeout(idle)
  }
}

export function ingestSync(req: IngestRequest): Promise<IngestResponse> {
  return request("/research/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}

export function ingestAsync(req: IngestRequest): Promise<AsyncIngestResponse> {
  return request("/research/ingest/async", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}

export function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return request(`/research/tasks/${taskId}`)
}

export interface SessionItem {
  session_id: string
  preview: string
  last_at: string | null
  message_count: number
}

export interface SessionMessage {
  role: "user" | "assistant"
  content: string
}

export function fetchSessions(): Promise<SessionItem[]> {
  return request("/research/sessions")
}

export function fetchSessionMessages(sessionId: string): Promise<SessionMessage[]> {
  return request(`/research/sessions/${sessionId}/messages`)
}

export async function uploadFile(file: File, title: string, domain: string): Promise<IngestResponse> {
  const form = new FormData()
  form.append("file", file)
  form.append("title", title)
  form.append("domain", domain)
  const res = await fetch(`${API_BASE}/research/upload`, {
    method: "POST",
    headers: authHeaders(),  // no Content-Type — browser sets the multipart boundary
    body: form,
  })
  if (res.status === 401) {
    handleUnauthorized()
    throw new Error("Unauthorized")
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text)
  }
  return res.json()
}

// ── Auth ──
export interface TokenResponse {
  access_token: string
  token_type: string
}

export async function register(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(typeof data?.detail === "string" ? data.detail : "Registration failed")
  }
  return res.json()
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(typeof data?.detail === "string" ? data.detail : "Login failed")
  }
  return res.json()
}

export function getMe(): Promise<{ id: string; email: string }> {
  return request("/auth/me")
}
