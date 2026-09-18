import { useEffect, useMemo } from "react"
import PDFViewer from "../search/PDFViewer"

/** Opens a cited source's document at the cited page. Close with Esc or the backdrop. */
export default function SourcePreviewModal({ source, query, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const results = useMemo(() => [source], [source])

  return (
    <div style={styles.backdrop} onClick={onClose}>
      <div
        style={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${source.filename}, page ${source.page_number}`}
      >
        <div style={styles.header}>
          <span style={styles.index}>[{source.index}]</span>
          <span style={styles.title} title={source.filename}>{source.filename}</span>
          <span style={styles.page}>p.{source.page_number}</span>
          <button onClick={onClose} style={styles.close} aria-label="Close">×</button>
        </div>
        <div style={styles.body}>
          <PDFViewer
            results={results}
            query={query}
            activeDocId={source.document_id}
            activePage={source.page_number}
          />
        </div>
      </div>
    </div>
  )
}

const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.6)",
    zIndex: 500,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  dialog: {
    width: "min(860px, 100%)",
    maxHeight: "100%",
    display: "flex",
    flexDirection: "column",
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 12px 10px 16px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  index: { fontSize: 12, fontWeight: 700, color: "var(--accent-hover)", fontFamily: "'JetBrains Mono', monospace" },
  title: {
    flex: 1,
    minWidth: 0,
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text-primary)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  page: { fontSize: 12, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" },
  close: {
    width: 28,
    height: 28,
    border: "none",
    borderRadius: 8,
    background: "var(--bg-hover)",
    color: "var(--text-secondary)",
    fontSize: 18,
    lineHeight: 1,
    cursor: "pointer",
  },
  body: { overflow: "auto", padding: 16 },
}
