import { API_BASE, csrfToken, refreshSession } from "../../shared/utils/axios"

export class AskError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

function post(body, signal) {
  return fetch(`${API_BASE}/ask/stream`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-CSRF-Token": csrfToken() || "",
    },
    body: JSON.stringify(body),
    signal,
  })
}

function parseEvent(block) {
  let event = "message"
  const data = []
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart())
  }
  return { event, data: data.length ? JSON.parse(data.join("\n")) : null }
}

/**
 * Asks a question and streams the answer (Server-Sent Events over POST, which
 * EventSource can't do). Callbacks: onSources(sources), onDelta(text), onDone({citations}).
 * Rejects with AskError; resolves when the stream ends. Abort via `signal`.
 */
export async function askStream({ question, documentIds, signal, onSources, onDelta, onDone }) {
  const body = { question, document_ids: documentIds?.length ? documentIds : null }

  let res = await post(body, signal)
  if (res.status === 401) {
    try {
      await refreshSession() // expired access cookie: refresh once, then retry
    } catch {
      throw new AskError("Your session has expired. Please sign in again.", 401)
    }
    res = await post(body, signal)
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const message =
      payload?.error?.message ||
      (res.status === 429 ? "Too many requests. Please wait a moment." : `Request failed (${res.status})`)
    throw new AskError(message, res.status)
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value.replace(/\r\n/g, "\n")

    let boundary
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      if (!block.trim()) continue

      const { event, data } = parseEvent(block)
      if (event === "sources") onSources?.(data)
      else if (event === "delta") onDelta?.(data.text)
      else if (event === "done") onDone?.(data)
      else if (event === "error") throw new AskError(data?.message || "The answer could not be generated.")
    }
  }
}
