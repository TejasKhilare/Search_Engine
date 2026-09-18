import { useEffect, useRef } from "react"
import { getDocument } from "../features/documents/api"
import { BUSY_STATUSES, useDocumentStore } from "../store/documentStore"
import { toast } from "../shared/utils/toast"

const POLL_MS = 2000

/**
 * While any document is pending/processing, polls just those documents and
 * announces when each finishes. Stops by itself when nothing is busy, and on unmount.
 */
export default function useDocumentPolling() {
  const busyIds = useDocumentStore((s) =>
    s.documents
      .filter((d) => BUSY_STATUSES.has(d.status))
      .map((d) => d.id)
      .join(",")
  )
  const inFlight = useRef(false)

  useEffect(() => {
    if (!busyIds) return

    const ids = busyIds.split(",")
    const timer = setInterval(async () => {
      if (inFlight.current) return // previous round still running
      inFlight.current = true
      try {
        const results = await Promise.allSettled(ids.map((id) => getDocument(id)))
        const { upsertDocument, removeDocument } = useDocumentStore.getState()
        results.forEach((result, i) => {
          if (result.status === "rejected") {
            if (result.reason?.response?.status === 404) removeDocument(ids[i]) // deleted elsewhere
            return
          }
          const doc = result.value
          upsertDocument(doc)
          if (doc.status === "ready") toast.success(`${doc.filename} is ready to search`)
          if (doc.status === "failed") toast.error(`${doc.filename}: ${doc.error_message || "processing failed"}`)
        })
      } finally {
        inFlight.current = false
      }
    }, POLL_MS)

    return () => clearInterval(timer)
  }, [busyIds])
}
