const CITATION_RE = /\[(\d+(?:\s*,\s*\d+)*)\]/g

/** Answer text with every [n] / [n, m] marker turned into a clickable citation. */
function AnswerText({ answer, sources, onOpenSource }) {
  const parts = []
  let last = 0
  for (const match of answer.matchAll(CITATION_RE)) {
    if (match.index > last) parts.push(answer.slice(last, match.index))
    for (const n of match[1].split(",").map((x) => Number(x.trim()))) {
      const source = sources[n - 1]
      parts.push(
        source ? (
          <button
            key={`${match.index}-${n}`}
            className="citation"
            onClick={() => onOpenSource(source)}
            title={`${source.filename}, page ${source.page_number}`}
          >
            {n}
          </button>
        ) : (
          `[${n}]`
        )
      )
    }
    last = match.index + match[0].length
  }
  if (last < answer.length) parts.push(answer.slice(last))
  return parts
}

export default function AnswerPanel({ phase, answer, sources, citations, error, onOpenSource }) {
  if (phase === "idle") {
    return (
      <div style={styles.emptyState}>
        <div style={styles.emptyIcon}>
          <svg width="40" height="40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
          </svg>
        </div>
        <p style={styles.emptyTitle}>Ask your documents anything</p>
        <p style={styles.emptyDesc}>Type a question above. The AI answers only from your documents and cites the pages it used. Click a [n] marker to open the source.</p>
        <div style={styles.examples}>
          <p style={styles.examplesLabel}>Example questions:</p>
          {["What are the main findings in this report?", "What skills does the candidate have?", "What is the project timeline and budget?"].map((ex, i) => (
            <div key={i} style={styles.example}>&ldquo;{ex}&rdquo;</div>
          ))}
        </div>
      </div>
    )
  }

  if (phase === "retrieving") {
    return (
      <div style={styles.loadingState}>
        <div style={styles.loadingPulse} />
        <div style={styles.loadingLines}>
          <div className="shimmer" style={{ ...styles.loadLine, width: "85%" }} />
          <div className="shimmer" style={{ ...styles.loadLine, width: "70%" }} />
          <div className="shimmer" style={{ ...styles.loadLine, width: "80%" }} />
        </div>
        <p style={styles.loadingText}>Searching your documents…</p>
      </div>
    )
  }

  const cited = new Set(citations)

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
        {phase === "error" && !answer ? (
          <p style={styles.errorText}>{error}</p>
        ) : (
          <p style={styles.answerText} className={phase === "streaming" ? "stream-caret" : undefined}>
            <AnswerText answer={answer} sources={sources} onOpenSource={onOpenSource} />
          </p>
        )}
        {phase === "error" && answer && <p style={styles.errorText}>{error}</p>}
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div style={styles.sourcesSection}>
          <h3 style={styles.sourcesTitle}>
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
            </svg>
            Sources ({sources.length})
          </h3>
          <div style={styles.sourcesList}>
            {sources.map((s) => (
              <button
                key={s.index}
                onClick={() => onOpenSource(s)}
                style={{ ...styles.sourceCard, ...(cited.has(s.index) ? styles.sourceCardCited : {}) }}
                title="Open this page"
                data-cited={cited.has(s.index) || undefined}
              >
                <div style={styles.sourceHeader}>
                  <div style={styles.sourceFile}>
                    <span style={styles.sourceIndex}>[{s.index}]</span>
                    {s.filename}
                  </div>
                  <div style={styles.sourceTags}>
                    {cited.has(s.index) && <span style={styles.citedTag}>cited</span>}
                    <span style={styles.pageTag}>p.{s.page_number}</span>
                    <span style={styles.scoreTag}>{(s.score * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <p style={styles.sourceExcerpt}>
                  {s.content.slice(0, 220)}{s.content.length > 220 ? "…" : ""}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const styles = {
  sourceCardCited: {
    borderColor: "rgba(124,106,247,0.55)",
    background: "rgba(124,106,247,0.07)",
  },
  citedTag: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--success)",
    border: "1px solid rgba(34,197,94,0.35)",
    borderRadius: 5,
    padding: "1px 6px",
  },
  sourceIndex: {
    color: "var(--accent-hover)",
    fontWeight: 700,
    fontFamily: "'JetBrains Mono', monospace",
    marginRight: 2,
  },
  errorText: {
    margin: "8px 0 0",
    fontSize: 13,
    color: "var(--error)",
  },
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
    width: "100%",
    textAlign: "left",
    color: "inherit",
    font: "inherit",
    cursor: "pointer",
    transition: "border-color 0.15s",
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