import { useState } from "react"
import { aiSearch } from "./api"
import useRag from "../../hooks/useRag"
import AnswerPanel from "./AnswerPanel"
import MainLayout from "../../shared/layout/MainLayout"
import Sidebar from "../documents/Sidebar"
import { toast } from "../../shared/utils/toast"

export default function AiSearchPage() {
  const [query, setQuery] = useState("")
  const { answer, setAnswer, sources, setSources, loading, setLoading, reset } = useRag()
  const [hasSearched, setHasSearched] = useState(false)

  const handleSearch = async () => {
    const q = query.trim()
    if (!q) return

    reset()
    setLoading(true)
    setHasSearched(true)

    try {
      const res = await aiSearch(q)
      setAnswer(res.answer)
      setSources(res.sources)
    } catch (err) {
      toast.error("AI search failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) handleSearch()
  }

  return (
    <MainLayout sidebar={<Sidebar />}>
      <div style={styles.page}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.titleRow}>
            <div style={styles.aiDot} />
            <h2 style={styles.title}>AI Ask</h2>
          </div>
          <p style={styles.subtitle}>Ask questions in natural language — get answers extracted from your documents.</p>

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
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              style={{
                ...styles.askBtn,
                opacity: (loading || !query.trim()) ? 0.6 : 1,
                cursor: (loading || !query.trim()) ? "not-allowed" : "pointer",
              }}
            >
              {loading ? (
                <span style={styles.spinner} />
              ) : (
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
                </svg>
              )}
            </button>
          </div>
          <p style={styles.hint}>Press Enter to send · Shift+Enter for new line</p>
        </div>

        {/* Answer panel */}
        <div style={styles.answerArea}>
          <AnswerPanel answer={answer} sources={sources} loading={loading} hasSearched={hasSearched} />
        </div>
      </div>
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
    margin: "8px 0 0",
  },
  answerArea: {
    flex: 1,
    overflow: "auto",
    padding: "20px 28px",
  },
}