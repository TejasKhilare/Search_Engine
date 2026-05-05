import { useState, memo, useCallback } from "react"
import MainLayout from "../../shared/layout/MainLayout"
import Sidebar from "../documents/Sidebar"
import PDFViewer from "./PDFViewer"
import useSearch from "../../hooks/useSearch"
import { searchDocuments } from "./api"
import { toast } from "../../shared/utils/toast"

const StablePDFViewer = memo(PDFViewer)

export default function SearchPage() {
  const { results, setResults, resetSearch } = useSearch()
  const [query, setQuery] = useState("")
  const [submittedQuery, setSubmittedQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  // Track which result the user clicked — drives the PDF viewer
  const [activePage, setActivePage] = useState(null)
  const [activeDocId, setActiveDocId] = useState(null)
  // For mobile: show PDF panel or results panel
  const [mobileView, setMobileView] = useState("results") // "results" | "pdf"

  const handleSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) return

    resetSearch()
    setLoading(true)
    setSearched(true)
    setActivePage(null)
    setActiveDocId(null)
    setMobileView("results")

    try {
      const data = await searchDocuments(q)
      setResults(data.results)
      setSubmittedQuery(q)
      if (data.results.length > 0) {
        setActiveDocId(data.results[0].doc_id)
        setActivePage(data.results[0].page_no)
      }
    } catch {
      toast.error("Search failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }, [query, resetSearch, setResults])

  const handleKeyDown = useCallback(
    (e) => { if (e.key === "Enter") handleSearch() },
    [handleSearch]
  )

  const handleClear = useCallback(() => {
    setQuery("")
    setSubmittedQuery("")
    resetSearch()
    setSearched(false)
    setActivePage(null)
    setActiveDocId(null)
    setMobileView("results")
  }, [resetSearch])

  // When user clicks a result card — navigate the PDF viewer
  const handleResultClick = useCallback((r) => {
    setActiveDocId(r.doc_id)
    setActivePage(r.page_no)
    setMobileView("pdf")
  }, [])

  return (
    <MainLayout sidebar={<Sidebar />}>
      <div style={styles.page}>
        {/* Search header */}
        <div style={styles.searchHeader}>
          <div style={styles.searchRow}>
            <div style={styles.searchBox}>
              <svg style={styles.searchIcon} width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607z" />
              </svg>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                style={styles.input}
                placeholder="Search your documents semantically..."
                autoFocus
              />
              {query && (
                <button onClick={handleClear} style={styles.clearBtn}>
                  <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              style={{
                ...styles.searchBtn,
                opacity: (loading || !query.trim()) ? 0.6 : 1,
                cursor: (loading || !query.trim()) ? "not-allowed" : "pointer",
              }}
            >
              {loading ? <span style={styles.spinner} /> : "Search"}
            </button>
          </div>

          {searched && !loading && (
            <div style={styles.metaRow}>
              <span style={styles.resultsMeta}>
                {results.length > 0
                  ? `${results.length} result${results.length !== 1 ? "s" : ""} found`
                  : "No results found"}
              </span>
              {/* Mobile toggle between results list and PDF */}
              {results.length > 0 && (
                <div style={styles.mobileToggle}>
                  <button
                    onClick={() => setMobileView("results")}
                    style={{
                      ...styles.toggleBtn,
                      background: mobileView === "results" ? "var(--accent)" : "var(--bg-hover)",
                      color: mobileView === "results" ? "#fff" : "var(--text-secondary)",
                    }}
                  >
                    Results
                  </button>
                  <button
                    onClick={() => setMobileView("pdf")}
                    style={{
                      ...styles.toggleBtn,
                      background: mobileView === "pdf" ? "var(--accent)" : "var(--bg-hover)",
                      color: mobileView === "pdf" ? "#fff" : "var(--text-secondary)",
                    }}
                  >
                    PDF
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Content */}
        <div style={styles.content}>
          {!searched && (
            <div style={styles.emptyState}>
              <div style={styles.emptyIcon}>
                <svg width="40" height="40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607z" />
                </svg>
              </div>
              <p style={styles.emptyTitle}>Semantic Document Search</p>
              <p style={styles.emptyDesc}>Search across all your uploaded PDFs using natural language. Results are ranked by semantic similarity.</p>
            </div>
          )}

          {searched && !loading && results.length === 0 && (
            <div style={styles.emptyState}>
              <p style={styles.emptyTitle}>No results found</p>
              <p style={styles.emptyDesc}>Try different keywords or upload more documents.</p>
            </div>
          )}

          {results.length > 0 && (
            <div style={styles.resultsLayout}>
              {/* Results list — hidden on mobile when PDF is shown */}
              <div
                style={{
                  ...styles.resultsList,
                  display: mobileView === "pdf" ? "none" : "flex",
                }}
                className="results-list-panel"
              >
                {results.map((r, i) => {
                  const isActive = activeDocId === r.doc_id && activePage === r.page_no
                  return (
                    <div
                      key={i}
                      style={{
                        ...styles.resultCard,
                        ...(isActive ? styles.resultCardActive : {}),
                      }}
                      className="fade-in"
                      onClick={() => handleResultClick(r)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === "Enter" && handleResultClick(r)}
                    >
                      <div style={styles.resultHeader}>
                        <div style={styles.resultDoc}>
                          <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                          </svg>
                          {r.filename}
                        </div>
                        <div style={styles.resultMeta}>
                          <span style={styles.pageTag}>p.{r.page_no}</span>
                          <span style={styles.scoreTag}>{(r.score * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <p style={styles.resultContent}>
                        {r.content.slice(0, 200)}{r.content.length > 200 ? "…" : ""}
                      </p>
                    </div>
                  )
                })}
              </div>

              {/* PDF Viewer — hidden on mobile when results list is shown */}
              <div
                style={{
                  ...styles.pdfArea,
                  display: mobileView === "results" ? "none" : "flex",
                }}
                className="pdf-area-panel"
              >
                <StablePDFViewer
                  results={results}
                  query={submittedQuery}
                  activePage={activePage}
                  activeDocId={activeDocId}
                />
              </div>

              {/* Desktop: always show both side by side */}
              <style>{`
                @media (min-width: 768px) {
                  .results-list-panel { display: flex !important; }
                  .pdf-area-panel { display: flex !important; }
                }
              `}</style>
            </div>
          )}
        </div>
      </div>
    </MainLayout>
  )
}

const styles = {
  page: { display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" },
  searchHeader: { padding: "16px 16px 12px", borderBottom: "1px solid var(--border)", flexShrink: 0 },
  searchRow: { display: "flex", gap: 10, alignItems: "center" },
  searchBox: {
    flex: 1, display: "flex", alignItems: "center",
    background: "var(--bg-card)", border: "1px solid var(--border)",
    borderRadius: 12, padding: "0 14px", gap: 10, transition: "border-color 0.15s",
    minWidth: 0,
  },
  searchIcon: { color: "var(--text-muted)", flexShrink: 0 },
  input: {
    flex: 1, background: "transparent", border: "none", outline: "none",
    fontSize: 14, color: "var(--text-primary)", fontFamily: "inherit", padding: "12px 0",
    minWidth: 0,
  },
  clearBtn: {
    display: "flex", alignItems: "center", background: "transparent",
    border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 2, flexShrink: 0,
  },
  searchBtn: {
    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
    padding: "11px 18px", background: "var(--accent)", border: "none", borderRadius: 12,
    color: "#fff", fontSize: 13, fontWeight: 600, fontFamily: "inherit",
    letterSpacing: "0.01em", minWidth: 72, flexShrink: 0,
  },
  spinner: {
    width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff", borderRadius: "50%", display: "inline-block",
    animation: "spin 0.8s linear infinite",
  },
  metaRow: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginTop: 8, flexWrap: "wrap", gap: 8,
  },
  resultsMeta: { fontSize: 12, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" },
  mobileToggle: { display: "flex", gap: 4 },
  toggleBtn: {
    border: "none", borderRadius: 8, padding: "4px 12px",
    fontSize: 12, fontWeight: 600, fontFamily: "inherit", cursor: "pointer",
    transition: "all 0.12s",
  },
  content: { flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" },
  emptyState: {
    display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center", flex: 1, gap: 10, padding: 40, color: "var(--text-muted)",
  },
  emptyIcon: {
    width: 72, height: 72, background: "var(--bg-card)", borderRadius: 20,
    display: "flex", alignItems: "center", justifyContent: "center",
    marginBottom: 4, color: "var(--border-light)",
  },
  emptyTitle: { fontSize: 15, fontWeight: 600, color: "var(--text-secondary)", margin: 0 },
  emptyDesc: { fontSize: 13, color: "var(--text-muted)", textAlign: "center", maxWidth: 400, lineHeight: 1.6, margin: 0 },
  resultsLayout: { display: "flex", flex: 1, overflow: "hidden", gap: 0 },
  resultsList: {
    width: 300, flexShrink: 0, overflowY: "auto",
    borderRight: "1px solid var(--border)", padding: "12px",
    flexDirection: "column", gap: 8,
  },
  resultCard: {
    background: "var(--bg-card)", border: "1px solid var(--border)",
    borderRadius: 12, padding: "12px 14px", cursor: "pointer", transition: "border-color 0.15s",
  },
  resultCardActive: {
    border: "1px solid var(--accent)",
    background: "var(--accent-glow)",
  },
  resultHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 8 },
  resultDoc: {
    display: "flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 600,
    color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em",
    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, minWidth: 0,
  },
  resultMeta: { display: "flex", gap: 4, flexShrink: 0 },
  pageTag: {
    padding: "2px 7px", background: "var(--bg-hover)", borderRadius: 6,
    fontSize: 11, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace",
  },
  scoreTag: {
    padding: "2px 7px", background: "var(--accent-glow)", borderRadius: 6,
    fontSize: 11, color: "var(--accent-hover)", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
  },
  resultContent: { fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 },
  pdfArea: {
    flex: 1, overflow: "auto", padding: "16px", flexDirection: "column",
    minWidth: 0,
  },
}