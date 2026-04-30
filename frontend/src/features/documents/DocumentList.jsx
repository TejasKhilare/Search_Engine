import { useEffect, useState } from "react"
import { fetchDocuments, deleteDocument } from "./api"
import { useDocumentStore } from "../../store/documentStore"
import { toast } from "../../shared/utils/toast"

export default function DocumentList() {
  const { documents, setDocuments, setSelectedDoc, selectedDoc, removeDocument } =
    useDocumentStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchDocuments()
        setDocuments(data)
      } catch {
        toast.error("Failed to load documents")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleDelete = async (e, docId) => {
    e.stopPropagation()
    try {
      await deleteDocument(docId)
      removeDocument(docId)
      toast.success("Document deleted")
    } catch {
      toast.error("Delete failed")
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
        const isSelected = selectedDoc?.doc_id === doc.doc_id
        return (
          <div
            key={doc.doc_id}
            style={{
              ...styles.item,
              ...(isSelected ? styles.itemSelected : {}),
            }}
            onClick={() => setSelectedDoc(doc)}
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
                <span className={`status-badge status-${doc.status}`}>
                  {doc.status}
                </span>
                {doc.total_chunks > 0 && (
                  <span style={styles.chunks}>{doc.total_chunks} chunks</span>
                )}
              </div>
            </div>

            <button
              onClick={(e) => handleDelete(e, doc.doc_id)}
              style={styles.deleteBtn}
              title="Delete document"
            >
              <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )
      })}
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