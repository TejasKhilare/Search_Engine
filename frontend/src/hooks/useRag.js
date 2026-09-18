import { useCallback, useEffect, useRef, useState } from "react"
import { askStream } from "../features/rag/api"

/**
 * State machine for one question/answer at a time:
 *   idle → retrieving (waiting for sources) → streaming (tokens arriving) → done | error
 * A new question or stop() aborts the one in flight.
 */
export default function useRag() {
  const [phase, setPhase] = useState("idle")
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState("")
  const [sources, setSources] = useState([])
  const [citations, setCitations] = useState([])
  const [error, setError] = useState(null)
  const controllerRef = useRef(null)

  const ask = useCallback(async (q, documentIds) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    setQuestion(q)
    setAnswer("")
    setSources([])
    setCitations([])
    setError(null)
    setPhase("retrieving")

    try {
      await askStream({
        question: q,
        documentIds,
        signal: controller.signal,
        onSources: (s) => setSources(s),
        onDelta: (text) => {
          setPhase("streaming")
          setAnswer((prev) => prev + text)
        },
        onDone: ({ citations: cited }) => setCitations(cited || []),
      })
      if (!controller.signal.aborted) setPhase("done")
    } catch (err) {
      if (controller.signal.aborted) return // stopped by the user or superseded
      setError(err.message || "Something went wrong")
      setPhase("error")
    }
  }, [])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    setPhase((p) => (p === "retrieving" || p === "streaming" ? "done" : p))
  }, [])

  // Abort any stream when leaving the page
  useEffect(() => () => controllerRef.current?.abort(), [])

  return {
    phase,
    busy: phase === "retrieving" || phase === "streaming",
    question,
    answer,
    sources,
    citations,
    error,
    ask,
    stop,
  }
}
