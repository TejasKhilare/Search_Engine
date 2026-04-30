export default function AnswerPanel({ answer, sources, loading, hasSearched }) {
  if (!hasSearched) {
    return (
      <div style={styles.emptyState}>
        <div style={styles.emptyIcon}>
          <svg width="40" height="40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
          </svg>
        </div>
        <p style={styles.emptyTitle}>Ask your documents anything</p>
        <p style={styles.emptyDesc}>Type a question above. The AI will search your documents and provide an answer with source references.</p>
        <div style={styles.examples}>
          <p style={styles.examplesLabel}>Example questions:</p>
          {["What are the main findings in this report?", "What skills does the candidate have?", "What is the project timeline and budget?"].map((ex, i) => (
            <div key={i} style={styles.example}>&ldquo;{ex}&rdquo;</div>
          ))}
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={styles.loadingState}>
        <div style={styles.loadingPulse} />
        <div style={styles.loadingLines}>
          <div className="shimmer" style={{ ...styles.loadLine, width: "85%" }} />
          <div className="shimmer" style={{ ...styles.loadLine, width: "70%" }} />
          <div className="shimmer" style={{ ...styles.loadLine, width: "80%" }} />
        </div>
        <p style={styles.loadingText}>Searching documents and generating answer...</p>
      </div>
    )
  }

  return (
    <div style={styles.container} className="fade-in">
      {/* Answer card */}
      <div style={styles.answerCard}>
        <div style={styles.answerHeader}>
          <div style={styles.answerBadge}>
            <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
            </svg>
            AI Answer
          </div>
        </div>
        <p style={styles.answerText}>{answer}</p>
      </div>

      {/* Sources */}
      {sources && sources.length > 0 && (
        <div style={styles.sourcesSection}>
          <h3 style={styles.sourcesTitle}>
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
            </svg>
            Sources ({sources.length})
          </h3>
          <div style={styles.sourcesList}>
            {sources.map((s, i) => (
              <div key={i} style={styles.sourceCard}>
                <div style={styles.sourceHeader}>
                  <div style={styles.sourceFile}>
                    <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                    </svg>
                    {s.filename}
                  </div>
                  <div style={styles.sourceTags}>
                    <span style={styles.pageTag}>p.{s.page_no}</span>
                    <span style={styles.scoreTag}>{(s.score * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <p style={styles.sourceExcerpt}>
                  {s.content.slice(0, 200)}{s.content.length > 200 ? "…" : ""}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: 20,
    maxWidth: 800,
  },
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    padding: "40px 20px",
    color: "var(--text-muted)",
    maxWidth: 480,
    margin: "0 auto",
  },
  emptyIcon: {
    width: 72,
    height: 72,
    background: "var(--bg-card)",
    borderRadius: 20,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
    color: "var(--border-light)",
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: "var(--text-secondary)",
    margin: 0,
  },
  emptyDesc: {
    fontSize: 13,
    color: "var(--text-muted)",
    textAlign: "center",
    lineHeight: 1.6,
    margin: 0,
  },
  examples: {
    marginTop: 16,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    width: "100%",
  },
  examplesLabel: {
    fontSize: 11,
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
    margin: "0 0 4px",
  },
  example: {
    fontSize: 12,
    color: "var(--text-secondary)",
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "8px 12px",
    fontStyle: "italic",
    lineHeight: 1.4,
  },
  loadingState: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    padding: "20px 0",
    maxWidth: 600,
  },
  loadingPulse: {
    width: 40,
    height: 40,
    borderRadius: "50%",
    background: "var(--accent-glow)",
    border: "2px solid var(--accent)",
    animation: "spin 1s linear infinite",
    marginBottom: 4,
  },
  loadingLines: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  loadLine: {
    height: 16,
    borderRadius: 8,
  },
  loadingText: {
    fontSize: 13,
    color: "var(--text-muted)",
    margin: 0,
  },
  answerCard: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: "20px 24px",
    borderLeft: "3px solid var(--accent)",
  },
  answerHeader: {
    marginBottom: 14,
  },
  answerBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 10px",
    background: "var(--accent-glow)",
    borderRadius: 100,
    fontSize: 11,
    fontWeight: 600,
    color: "var(--accent-hover)",
    letterSpacing: "0.02em",
    textTransform: "uppercase",
  },
  answerText: {
    fontSize: 14,
    color: "var(--text-primary)",
    lineHeight: 1.7,
    margin: 0,
    whiteSpace: "pre-line",
  },
  sourcesSection: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  sourcesTitle: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    margin: 0,
  },
  sourcesList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  sourceCard: {
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "12px 16px",
  },
  sourceHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
    gap: 8,
  },
  sourceFile: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
    minWidth: 0,
  },
  sourceTags: {
    display: "flex",
    gap: 4,
    flexShrink: 0,
  },
  pageTag: {
    padding: "2px 7px",
    background: "var(--bg-hover)",
    borderRadius: 6,
    fontSize: 11,
    color: "var(--text-muted)",
    fontFamily: "'JetBrains Mono', monospace",
  },
  scoreTag: {
    padding: "2px 7px",
    background: "var(--accent-glow)",
    borderRadius: 6,
    fontSize: 11,
    color: "var(--accent-hover)",
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: 600,
  },
  sourceExcerpt: {
    fontSize: 12,
    color: "var(--text-muted)",
    lineHeight: 1.6,
    margin: 0,
  },
}