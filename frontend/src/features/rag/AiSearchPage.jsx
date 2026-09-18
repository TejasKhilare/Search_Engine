import { useCallback, useState } from "react"
import useRag from "../../hooks/useRag"
import AnswerPanel from "./AnswerPanel"
import SourcePreviewModal from "./SourcePreviewModal"
import MainLayout from "../../shared/layout/MainLayout"
import ScopeChip from "../../shared/components/ScopeChip"
import Sidebar from "../documents/Sidebar"
import { useDocumentStore } from "../../store/documentStore"

export default function AiSearchPage() {
  const [query, setQuery] = useState("")
  const [openSource, setOpenSource] = useState(null)
  const { phase, busy, question, answer, sources, citations, error, ask, stop } = useRag()
  const scopeId = useDocumentStore((s) => s.selectedDoc?.id ?? null)

  const handleSearch = () => {
    const q = query.trim()
    if (!q || busy) return
    ask(q, scopeId ? [scopeId] : null)
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSearch()
    }
  }

  const closePreview = useCallback(() => setOpenSource(null), [])

  return (
    <MainLayout sidebar={<Sidebar />}>
      <div style={styles.page}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.titleRow}>
            <div style={styles.aiDot} />
            <h2 style={styles.title}>AI Ask</h2>
          </div>
          <p style={styles.subtitle}>Ask questions in natural language — answers come only from your documents, with page citations.</p>

          {/* Search input */}
          <div style={styles.inputRow}>
            <div style={styles.textareaWrap}>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything about your documents..."
                style={styles.textarea}
                rows={2}
                maxLength={2000}
              />
            </div>
            {busy ? (
              <button onClick={stop} style={{ ...styles.askBtn, background: "var(--bg-hover)" }} title="Stop" aria-label="Stop generating">
                <span style={styles.stopIcon} />
              </button>
            ) : (
              <button
                onClick={handleSearch}
                disabled={!query.trim()}
                aria-label="Ask"
                style={{
                  ...styles.askBtn,
                  opacity: !query.trim() ? 0.6 : 1,
                  cursor: !query.trim() ? "not-allowed" : "pointer",
                }}
              >
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
                </svg>
              </button>
            )}
          </div>
          <div style={styles.metaRow}>
            <ScopeChip />
            <p style={styles.hint}>Enter to send · Shift+Enter for new line</p>
          </div>
        </div>

        {/* Answer panel */}
        <div style={styles.answerArea}>
          <AnswerPanel
            phase={phase}
            answer={answer}
            sources={sources}
            citations={citations}
            error={error}
            onOpenSource={setOpenSource}
          />
        </div>
      </div>

      {openSource && <SourcePreviewModal source={openSource} query={question} onClose={closePreview} />}
    </MainLayout>
  )
}

const styles = {
  page: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    overflow: "hidden",
  },
  header: {
    padding: "24px 28px 20px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  titleRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 4,
  },
  aiDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "var(--accent)",
    boxShadow: "0 0 8px var(--accent)",
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: 0,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-muted)",
    margin: "0 0 16px",
  },
  inputRow: {
    display: "flex",
    gap: 10,
    alignItems: "flex-end",
  },
  textareaWrap: {
    flex: 1,
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: 14,
    overflow: "hidden",
    transition: "border-color 0.15s",
  },
  textarea: {
    width: "100%",
    background: "transparent",
    border: "none",
    outline: "none",
    padding: "13px 16px",
    fontSize: 14,
    color: "var(--text-primary)",
    fontFamily: "inherit",
    resize: "none",
    lineHeight: 1.5,
  },
  askBtn: {
    width: 44,
    height: 44,
    background: "var(--accent)",
    border: "none",
    borderRadius: 12,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#fff",
    flexShrink: 0,
    transition: "background 0.15s",
  },
  spinner: {
    width: 16,
    height: 16,
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    display: "inline-block",
    animation: "spin 0.8s linear infinite",
  },
  hint: {
    fontSize: 11,
    color: "var(--text-muted)",
    margin: 0,
    flexShrink: 0,
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    marginTop: 8,
    flexWrap: "wrap",
    minWidth: 0,
  },
  stopIcon: {
    width: 12,
    height: 12,
    borderRadius: 2,
    background: "var(--text-primary)",
  },
  answerArea: {
    flex: 1,
    overflow: "auto",
    padding: "20px 28px",
  },
}