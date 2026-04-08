"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { getTaskStatus, ingestAsync, uploadFile } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"

const DOMAINS = [
  { value: "ml", label: "ML / AI" },
  { value: "dl", label: "Deep Learning" },
  { value: "cs", label: "Computer Science" },
  { value: "physics", label: "Physics" },
  { value: "bio", label: "Biology" },
  { value: "finance", label: "Finance" },
  { value: "math", label: "Mathematics" },
]

interface IngestResult {
  taskId?: string
  documentId?: string
  status: string
}

export default function IngestPage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const [title, setTitle] = useState("")
  const [domain, setDomain] = useState("ml")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [taskStatus, setTaskStatus] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [urlSource, setUrlSource] = useState("")
  const [tab, setTab] = useState<"file" | "url">("file")
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login")
  }, [authLoading, user, router])

  function startPolling(taskId: string) {
    pollRef.current = setInterval(async () => {
      try {
        const s = await getTaskStatus(taskId)
        setTaskStatus(s.status)
        if (s.status === "completed" || s.status === "failed") clearInterval(pollRef.current!)
      } catch { clearInterval(pollRef.current!) }
    }, 3000)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (!file) return
    setSelectedFile(file)
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""))
  }, [title])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""))
  }

  async function handleSubmit() {
    const t = title.trim()
    if (!t || loading) return
    setLoading(true); setError(null); setResult(null); setTaskStatus(null)
    try {
      if (tab === "file") {
        if (!selectedFile) { setError("Please select a file"); setLoading(false); return }
        const res = await uploadFile(selectedFile, t, domain)
        setResult({ documentId: res.document_id, status: res.status })
      } else {
        const u = urlSource.trim()
        if (!u) { setError("Please enter a URL"); setLoading(false); return }
        const res = await ingestAsync({ title: t, source: u, domain })
        setResult({ taskId: res.task_id, status: res.status })
        startPolling(res.task_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed")
    } finally { setLoading(false) }
  }

  const currentStatus = taskStatus ?? result?.status ?? ""

  if (authLoading || !user) {
    return (
      <div className="flex h-screen items-center justify-center"
        style={{ background: "var(--background)", color: "var(--muted-foreground)" }}>Loading…</div>
    )
  }

  return (
    <div className="flex h-screen" style={{ background: "var(--background)", color: "var(--foreground)" }}>

      {/* Sidebar */}
      <aside className="w-60 shrink-0 flex flex-col" style={{ background: "var(--sidebar)", borderRight: "1px solid var(--sidebar-border)" }}>
        <div className="px-5 py-5" style={{ borderBottom: "1px solid var(--sidebar-border)" }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-base font-bold"
              style={{ background: "linear-gradient(135deg, #4f8ef7 0%, #7c5df7 100%)" }}>
              V
            </div>
            <div>
              <p className="font-semibold text-[15px] leading-tight" style={{ color: "var(--foreground)" }}>Verity</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--muted-foreground)" }}>AI Research Assistant</p>
            </div>
          </div>
        </div>

        <div className="px-3 py-4 flex-1">
          <p className="text-xs font-semibold uppercase tracking-widest px-2 mb-3" style={{ color: "var(--muted-foreground)" }}>
            Navigation
          </p>
          <Link href="/" className="block">
            <button className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-all"
              style={{ color: "var(--muted-foreground)" }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.06)"; (e.currentTarget as HTMLElement).style.color = "var(--foreground)" }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = ""; (e.currentTarget as HTMLElement).style.color = "var(--muted-foreground)" }}
            >
              ← Back to Chat
            </button>
          </Link>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-xl mx-auto px-6 py-12">

          <div className="mb-8">
            <h1 className="text-2xl font-semibold mb-2" style={{ color: "var(--foreground)" }}>Add Document</h1>
            <p className="text-base" style={{ color: "var(--muted-foreground)" }}>
              Upload a PDF or paste a URL — runs through the full ingestion pipeline: parse → chunk → embed → store.
            </p>
          </div>

          <div className="rounded-2xl p-6 space-y-5" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>

            {/* Tab selector */}
            <div className="flex gap-1 p-1 rounded-xl" style={{ background: "var(--secondary)" }}>
              {(["file", "url"] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
                  style={tab === t ? {
                    background: "var(--card)",
                    color: "var(--foreground)",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                  } : {
                    color: "var(--muted-foreground)",
                  }}
                >
                  {t === "file" ? "Upload PDF" : "URL / Path"}
                </button>
              ))}
            </div>

            {/* File drag & drop */}
            {tab === "file" && (
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all"
                style={dragOver ? {
                  borderColor: "#4f8ef7",
                  background: "rgba(79,142,247,0.06)",
                } : selectedFile ? {
                  borderColor: "#34d399",
                  background: "rgba(52,211,153,0.06)",
                } : {
                  borderColor: "var(--border)",
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,.docx"
                  className="hidden"
                  onChange={handleFileChange}
                />
                {selectedFile ? (
                  <div>
                    <div className="text-3xl mb-3">📄</div>
                    <p className="text-base font-medium" style={{ color: "#34d399" }}>{selectedFile.name}</p>
                    <p className="text-sm mt-1" style={{ color: "var(--muted-foreground)" }}>
                      {(selectedFile.size / 1024).toFixed(0)} KB · Click to change
                    </p>
                  </div>
                ) : (
                  <div>
                    <div className="text-3xl mb-3 opacity-40">📁</div>
                    <p className="text-base font-medium" style={{ color: "var(--foreground)" }}>Drag & drop your file here</p>
                    <p className="text-sm mt-1" style={{ color: "var(--muted-foreground)" }}>
                      or click to browse · PDF, TXT, DOCX, MD
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* URL input */}
            {tab === "url" && (
              <div className="space-y-2">
                <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>URL or File Path</label>
                <input
                  value={urlSource}
                  onChange={e => setUrlSource(e.target.value)}
                  placeholder="https://arxiv.org/pdf/2005.11401"
                  disabled={loading}
                  className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none transition-all"
                  style={{
                    background: "var(--secondary)",
                    border: "1px solid var(--border)",
                    color: "var(--foreground)",
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = "#4f8ef7" }}
                  onBlur={e => { e.currentTarget.style.borderColor = "var(--border)" }}
                />
              </div>
            )}

            {/* Title */}
            <div className="space-y-2">
              <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Document Title</label>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Attention Is All You Need"
                disabled={loading}
                className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none transition-all"
                style={{
                  background: "var(--secondary)",
                  border: "1px solid var(--border)",
                  color: "var(--foreground)",
                }}
                onFocus={e => { e.currentTarget.style.borderColor = "#4f8ef7" }}
                onBlur={e => { e.currentTarget.style.borderColor = "var(--border)" }}
              />
            </div>

            {/* Domain */}
            <div className="space-y-2">
              <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Domain</label>
              <select
                value={domain}
                onChange={e => setDomain(e.target.value)}
                disabled={loading}
                className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none transition-all appearance-none"
                style={{
                  background: "var(--secondary)",
                  border: "1px solid var(--border)",
                  color: "var(--foreground)",
                }}
              >
                {DOMAINS.map(d => (
                  <option key={d.value} value={d.value} style={{ background: "var(--card)" }}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={loading || !title.trim() || (tab === "file" ? !selectedFile : !urlSource.trim())}
              className="w-full py-3 rounded-xl text-base font-semibold text-white transition-all"
              style={loading || !title.trim() || (tab === "file" ? !selectedFile : !urlSource.trim()) ? {
                background: "var(--secondary)",
                color: "var(--muted-foreground)",
                cursor: "not-allowed",
              } : {
                background: "linear-gradient(135deg, #4f8ef7 0%, #3a7aec 100%)",
                boxShadow: "0 4px 16px rgba(79,142,247,0.35)",
              }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Ingesting…
                </span>
              ) : "Ingest Document"}
            </button>

            {/* Error */}
            {error && (
              <div className="rounded-xl px-4 py-3.5 text-sm"
                style={{ background: "rgba(229,87,87,0.1)", border: "1px solid rgba(229,87,87,0.25)", color: "#e57373" }}>
                {error}
              </div>
            )}

            {/* Result */}
            {result && (() => {
              const statusMap: Record<string, { bg: string; color: string; label: string }> = {
                completed: { bg: "rgba(52,211,153,0.1)", color: "#34d399", label: "Completed" },
                failed: { bg: "rgba(229,87,87,0.1)", color: "#e57373", label: "Failed" },
                running: { bg: "rgba(79,142,247,0.1)", color: "#4f8ef7", label: "Running…" },
                queued: { bg: "rgba(251,191,36,0.1)", color: "#fbbf24", label: "Queued…" },
              }
              const s = statusMap[currentStatus] ?? { bg: "var(--secondary)", color: "var(--muted-foreground)", label: currentStatus }
              return (
                <div className="rounded-xl px-4 py-4 space-y-2"
                  style={{ background: s.bg, border: `1px solid ${s.color}30` }}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Status</span>
                    <span className="text-sm font-semibold" style={{ color: s.color }}>{s.label}</span>
                  </div>
                  {result.taskId && (
                    <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                      Task: <code className="font-mono">{result.taskId}</code>
                    </p>
                  )}
                  {result.documentId && (
                    <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                      Doc ID: <code className="font-mono">{result.documentId}</code>
                    </p>
                  )}
                </div>
              )
            })()}
          </div>
        </div>
      </div>
    </div>
  )
}
