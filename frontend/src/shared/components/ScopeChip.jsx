import { useDocumentStore } from "../../store/documentStore"

/** Shows what a search/question covers; the scope is set by selecting a document in the sidebar. */
export default function ScopeChip() {
  const selectedDoc = useDocumentStore((s) => s.selectedDoc)
  const clearSelectedDoc = useDocumentStore((s) => s.clearSelectedDoc)

  if (!selectedDoc) {
    return <span style={styles.hint}>Searching all documents · select one in the sidebar to narrow down</span>
  }

  return (
    <span style={styles.chip} title={selectedDoc.filename}>
      <span style={styles.label}>In:</span>
      <span style={styles.name}>{selectedDoc.filename}</span>
      <button onClick={clearSelectedDoc} style={styles.clear} aria-label="Search all documents">
        ×
      </button>
    </span>
  )
}

const styles = {
  hint: { fontSize: 11, color: "var(--text-muted)" },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    maxWidth: "100%",
    padding: "3px 4px 3px 10px",
    background: "var(--accent-glow)",
    border: "1px solid rgba(124,106,247,0.35)",
    borderRadius: 100,
    fontSize: 12,
    color: "var(--text-primary)",
  },
  label: { color: "var(--text-secondary)", flexShrink: 0 },
  name: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 500 },
  clear: {
    width: 20,
    height: 20,
    flexShrink: 0,
    border: "none",
    borderRadius: "50%",
    background: "transparent",
    color: "var(--text-secondary)",
    fontSize: 15,
    lineHeight: 1,
    cursor: "pointer",
  },
}
