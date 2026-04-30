import DocumentList from "./DocumentList"
import UploadButton from "./UploadButton"

export default function Sidebar() {
  return (
    <div style={styles.sidebar}>
      <div style={styles.header}>
        <span style={styles.title}>Documents</span>
      </div>

      <div style={styles.uploadArea}>
        <UploadButton />
      </div>

      <div style={styles.listArea}>
        <DocumentList />
      </div>
    </div>
  )
}

const styles = {
  sidebar: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    background: "var(--bg-secondary)",
    overflow: "hidden",
  },
  header: {
    padding: "18px 16px 12px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  title: {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--text-muted)",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  uploadArea: {
    padding: "12px 12px 8px",
    flexShrink: 0,
  },
  listArea: {
    flex: 1,
    overflowY: "auto",
    padding: "4px 8px 16px",
  },
}