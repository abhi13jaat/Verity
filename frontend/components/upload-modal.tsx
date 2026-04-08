"use client"

import { useCallback, useRef, useState } from "react"
import { uploadFile } from "@/lib/api"

const DOMAINS = [
  { value: "ml", label: "ML / AI" },
  { value: "dl", label: "Deep Learning" },
  { value: "cs", label: "Computer Science" },
  { value: "physics", label: "Physics" },
  { value: "bio", label: "Biology" },
  { value: "finance", label: "Finance" },
  { value: "math", label: "Mathematics" },
]

interface UploadModalProps {
  /** The chat's current domain — used as the default ("all" falls back to "ml"). */
  defaultDomain: string
  onClose: () => void
  /** Called after a successful upload with the (mandatory) document title. */
  onUploaded: (title: string) => void
}

export function UploadModal({ defaultDomain, onClose, onUploaded }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState("")
  const [domain, setDomain] = useState(defaultDomain === "all" ? "ml" : defaultDomain)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const pickFile = useCallback((f: File | null | undefined) => {
    if (!f) return
    setFile(f)
    setTitle(prev => prev.trim() ? prev : f.name.replace(/\.[^.]+$/, ""))
  }, [])

  const canSubmit = !!file && !!title.trim() && !uploading

  async function submit() {
    if (!canSubmit || !file) return
    setUploading(true)
    setError(null)
    try {
      await uploadFile(file, title.trim(), domain)
      onUploaded(title.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
      setUploading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)" }}
      onClick={() => { if (!uploading) onClose() }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-6 space-y-5"
        style={{ background: "var(--card)", border: "1px solid var(--border)", boxShadow: "0 24px 64px rgba(0,0,0,0.5)" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold" style={{ color: "var(--foreground)" }}>Add Document</h2>
            <p className="text-sm mt-1" style={{ color: "var(--muted-foreground)" }}>
              Upload a paper — it starts a new chat you can discuss it in.
            </p>
          </div>
          <button
            onClick={() => { if (!uploading) onClose() }}
            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-base transition-all"
            style={{ color: "var(--muted-foreground)" }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.06)" }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = "" }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Drag & drop */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); pickFile(e.dataTransfer.files[0]) }}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all"
          style={dragOver ? { borderColor: "#4f8ef7", background: "rgba(79,142,247,0.06)" }
            : file ? { borderColor: "#34d399", background: "rgba(52,211,153,0.06)" }
            : { borderColor: "var(--border)" }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.docx"
            className="hidden"
            onChange={e => pickFile(e.target.files?.[0])}
          />
          {file ? (
            <div>
              <div className="text-3xl mb-2">📄</div>
              <p className="text-base font-medium" style={{ color: "#34d399" }}>{file.name}</p>
              <p className="text-sm mt-1" style={{ color: "var(--muted-foreground)" }}>
                {(file.size / 1024).toFixed(0)} KB · Click to change
              </p>
            </div>
          ) : (
            <div>
              <div className="text-3xl mb-2 opacity-40">📁</div>
              <p className="text-base font-medium" style={{ color: "var(--foreground)" }}>Drag &amp; drop your file here</p>
              <p className="text-sm mt-1" style={{ color: "var(--muted-foreground)" }}>
                or click to browse · PDF, TXT, DOCX, MD
              </p>
            </div>
          )}
        </div>

        {/* Title (required) */}
        <div className="space-y-2">
          <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
            Document Title <span style={{ color: "#e57373" }}>*</span>
          </label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Attention Is All You Need"
            disabled={uploading}
            className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none transition-all"
            style={{ background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)" }}
            onFocus={e => { e.currentTarget.style.borderColor = "#4f8ef7" }}
            onBlur={e => { e.currentTarget.style.borderColor = "var(--border)" }}
          />
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>This names the new chat.</p>
        </div>

        {/* Domain */}
        <div className="space-y-2">
          <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Domain</label>
          <select
            value={domain}
            onChange={e => setDomain(e.target.value)}
            disabled={uploading}
            className="w-full px-3.5 py-2.5 rounded-xl text-base outline-none transition-all appearance-none cursor-pointer"
            style={{ background: "var(--secondary)", border: "1px solid var(--border)", color: "var(--foreground)" }}
          >
            {DOMAINS.map(d => (
              <option key={d.value} value={d.value} style={{ background: "var(--card)" }}>{d.label}</option>
            ))}
          </select>
        </div>

        {error && (
          <div className="rounded-xl px-4 py-3 text-sm"
            style={{ background: "rgba(229,87,87,0.1)", border: "1px solid rgba(229,87,87,0.25)", color: "#e57373" }}>
            {error}
          </div>
        )}

        {/* Upload */}
        <button
          onClick={submit}
          disabled={!canSubmit}
          className="w-full py-3 rounded-xl text-base font-semibold text-white transition-all"
          style={!canSubmit ? {
            background: "var(--secondary)", color: "var(--muted-foreground)", cursor: "not-allowed",
          } : {
            background: "linear-gradient(135deg, #4f8ef7 0%, #3a7aec 100%)", boxShadow: "0 4px 16px rgba(79,142,247,0.35)",
          }}
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              Uploading &amp; indexing…
            </span>
          ) : "Upload & Start Chat"}
        </button>
      </div>
    </div>
  )
}
