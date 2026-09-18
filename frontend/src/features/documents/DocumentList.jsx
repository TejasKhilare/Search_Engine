import { useEffect, useState } from "react"
import { deleteDocument, fetchDocuments, reprocessDocument } from "./api"
import { useDocumentStore } from "../../store/documentStore"
import useDocumentPolling from "../../hooks/useDocumentPolling"
import { getErrorMessage } from "../../shared/utils/axios"
import { toast } from "../../shared/utils/toast"

const PAGE_SIZE = 50

export default function DocumentList() {
  const { documents, total, loaded, selectedDoc, setPage, toggleSelectedDoc, removeDocument, upsertDocument } =
    useDocumentStore()
  const [loading, setLoading] = useState(!loaded)
  const [loadingMore, setLoadingMore] = useState(false)

  useDocumentPolling()

  useEffect(() => {
    // Loaded once per session; later changes come from uploads, polling and deletes
    if (useDocumentStore.getState().loaded) return
    fetchDocuments({ limit: PAGE_SIZE })
      .then((page) => setPage(page))
      .catch((err) => toast.error(getErrorMessage(err, "Failed to load documents")))
      .finally(() => setLoading(false))
  }, [setPage])

  const handleLoadMore = async () => {
    setLoadingMore(true)
    try {
      setPage(await fetchDocuments({ limit: PAGE_SIZE, offset: documents.length }), { append: true })
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to load documents"))
    } finally {
      setLoadingMore(false)
    }
  }

  const handleDelete = async (e, doc) => {
    e.stopPropagation()
    if (!window.confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return
    try {
      await deleteDocument(doc.id)
      removeDocument(doc.id)
      toast.success("Document deleted")
    } catch (err) {
      toast.error(getErrorMessage(err, "Delete failed"))
    }
  }

  const handleRetry = async (e, doc) => {
    e.stopPropagation()
    try {
      upsertDocument(await reprocessDocument(doc.id)) // back to "pending"; polling takes over
      toast.info(`Reprocessing ${doc.filename}…`)
    } catch (err) {
      toast.error(getErrorMessage(err, "Could not reprocess"))
    }
  }

  if (loading) {
    return (
      <div style={styles.loading}>
        {[1, 2, 3].map((i) => (
          <div key={i} className="shimmer" style={styles.skeleton} />
        ))}
      </div>
    )
  }

  if (!documents.length) {
    return (
      <div style={styles.empty}>
        <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1} style={{ color: "var(--text-muted)" }}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
        </svg>
        <p style={styles.emptyText}>No documents yet</p>
        <p style={styles.emptySubText}>Upload a PDF to get started</p>
      </div>
    )
  }

  return (
    <div style={styles.list}>
      {documents.map((doc) => {
        const isSelected = selectedDoc?.id === doc.id
        const canSelect = doc.status === "ready"
        return (
          <div
            key={doc.id}
            style={{
              ...styles.item,
              ...(isSelected ? styles.itemSelected : {}),
              cursor: canSelect ? "pointer" : "default",
            }}
            onClick={() => canSelect && toggleSelectedDoc(doc)}
            title={canSelect ? (isSelected ? "Click to search all documents" : "Click to search only this document") : undefined}
          >
            <div style={styles.docIcon}>
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
            </div>

            <div style={styles.docInfo}>
              <div style={styles.docName} title={doc.filename}>
                {doc.filename}
              </div>
              <div style={styles.docMeta}>
                <span className={`status-badge status-${doc.status}`} title={doc.error_message || undefined}>
                  {doc.status}
                </span>
                {doc.status === "ready" && (
                  <span style={styles.chunks}>
                    {doc.page_count ?? "?"} pages · {doc.chunk_count} chunks
                  </span>
                )}
                {doc.status === "failed" && (
                  <button onClick={(e) => handleRetry(e, doc)} style={styles.retryBtn} title={doc.error_message || "Retry"}>
                    ↻ Retry
                  </button>
                )}
              </div>
            </div>

            <button
              onClick={(e) => handleDelete(e, doc)}
              style={styles.deleteBtn}
              title="Delete document"
              aria-label={`Delete ${doc.filename}`}
            >
              <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )
      })}

      {documents.length < total && (
        <button onClick={handleLoadMore} disabled={loadingMore} style={styles.loadMore}>
          {loadingMore ? "Loading…" : `Load more (${total - documents.length})`}
        </button>
      )}
    </div>
  )
}

const styles = {
  list: { display: "flex", flexDirection: "column", gap: 2 },
  loading: { display: "flex", flexDirection: "column", gap: 6, padding: "4px 0" },
  skeleton: { height: 56, borderRadius: 10 },
  empty: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "32px 16px",
    gap: 6,
  },
  emptyText: { fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", margin: 0 },
  emptySubText: { fontSize: 12, color: "var(--text-muted)", margin: 0, textAlign: "center" },
  item: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 8px",
    borderRadius: 10,
    cursor: "pointer",
    transition: "background 0.12s",
    border: "1px solid transparent",
    minWidth: 0,
  },
  itemSelected: {
    background: "var(--accent-glow)",
    border: "1px solid rgba(124,106,247,0.25)",
  },
  docIcon: {
    width: 30,
    height: 30,
    background: "var(--bg-card)",
    borderRadius: 7,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    color: "var(--text-muted)",
  },
  docInfo: {
    flex: 1,
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 3,
  },
  docName: {
    fontSize: 12,
    fontWeight: 500,
    color: "var(--text-primary)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    lineHeight: 1.3,
  },
  docMeta: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
  chunks: {
    fontSize: 10,
    color: "var(--text-muted)",
    fontFamily: "'JetBrains Mono', monospace",
  },
  retryBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 3,
    background: "transparent",
    border: "none",
    padding: 0,
    fontSize: 10,
    fontWeight: 600,
    color: "var(--accent-hover)",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  loadMore: {
    marginTop: 6,
    padding: "7px 0",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text-secondary)",
    fontSize: 12,
    fontFamily: "inherit",
    cursor: "pointer",
  },
  deleteBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 24,
    height: 24,
    background: "transparent",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    color: "var(--text-muted)",
    flexShrink: 0,
    transition: "all 0.12s",
    padding: 0,
  },
}