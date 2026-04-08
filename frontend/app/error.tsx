"use client"

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div
      className="flex h-screen flex-col items-center justify-center gap-4 text-center px-6"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
        style={{ background: "rgba(229,87,87,0.12)", border: "1px solid rgba(229,87,87,0.3)" }}
      >
        ⚠️
      </div>
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="text-sm max-w-sm" style={{ color: "var(--muted-foreground)" }}>
        An unexpected error occurred in the app. You can try again — your chats are saved.
      </p>
      <button
        onClick={reset}
        className="mt-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white"
        style={{ background: "linear-gradient(135deg, #4f8ef7 0%, #3a7aec 100%)" }}
      >
        Try again
      </button>
    </div>
  )
}
