import { Document, Page, pdfjs } from "react-pdf"
import { useState, useMemo, useRef, useCallback, memo, useEffect } from "react"
import "react-pdf/dist/Page/TextLayer.css"
import "react-pdf/dist/Page/AnnotationLayer.css"
import HighlightLayer from "./HighlightLayer"

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

// ─── Hook: watch container width via ResizeObserver ──────────────────────────
function useContainerWidth(ref) {
  const [width, setWidth] = useState(600)

  useEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = Math.floor(entry.contentRect.width)
        if (w > 0) setWidth(w)
      }
    })
    ro.observe(ref.current)
    const initial = Math.floor(ref.current.getBoundingClientRect().width)
    if (initial > 0) setWidth(initial)
    return () => ro.disconnect()
  }, [ref])

  return width
}

// ─── Single document viewer ───────────────────────────────────────────────────
function SingleDocViewer({ docResults, query, activePage, fileProp }) {
  const containerRef = useRef(null)
  const pageWrapperRef = useRef(null)
  const containerWidth = useContainerWidth(containerRef)

  const [numPages, setNumPages] = useState(null)
  const [pageNum, setPageNum] = useState(docResults[0]?.page_no || 1)
  const [pageReady, setPageReady] = useState(false)
  const [renderedSize, setRenderedSize] = useState(null)

  // Track whether we've set the initial page for this document load
  const initializedRef = useRef(false)

  // Pages that have search results
  const resultPages = useMemo(
    () => [...new Set(docResults.map((r) => r.page_no))].sort((a, b) => a - b),
    [docResults]
  )

  // OCR/extracted text for the currently viewed page (for image PDF highlight fallback)
  const chunkText = useMemo(() => {
    const chunks = docResults.filter((r) => r.page_no === pageNum)
    return chunks.map((r) => r.content).join(" ")
  }, [docResults, pageNum])

  // Sync to activePage prop (result card clicks from SearchPage)
  useEffect(() => {
    if (activePage && activePage !== pageNum) {
      setPageReady(false)
      setRenderedSize(null)
      setPageNum(activePage)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePage])

  // Called once when PDF loads — only set page on first load
  const handleLoadSuccess = useCallback(({ numPages: n }) => {
    setNumPages(n)
    if (!initializedRef.current) {
      initializedRef.current = true
      // Don't reset pageNum here — activePage useEffect handles it
    }
    setPageReady(false)
    setRenderedSize(null)
  }, [])

  // After page renders, measure the actual canvas pixel size for highlight coord mapping
  const handleRenderSuccess = useCallback(() => {
    setPageReady(true)
    if (pageWrapperRef.current) {
      const canvas = pageWrapperRef.current.querySelector("canvas")
      if (canvas) {
        const rect = canvas.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          setRenderedSize({ width: rect.width, height: rect.height })
        }
      }
    }
  }, [])

  const goToPage = useCallback((p) => {
    setPageReady(false)
    setRenderedSize(null)
    setPageNum(p)
  }, [])

  const handlePrev = useCallback(
    () => goToPage(Math.max(1, pageNum - 1)),
    [pageNum, goToPage]
  )

  const handleNext = useCallback(
    () => goToPage(Math.min(numPages || 1, pageNum + 1)),
    [pageNum, numPages, goToPage]
  )

  return (
    <div style={styles.docViewer} ref={containerRef}>

      {/* Result page jump buttons */}
      {resultPages.length > 0 && (
        <div style={styles.jumpBar}>
          <span style={styles.jumpLabel}>Results on pages:</span>
          {resultPages.map((p) => (
            <button
              key={p}
              onClick={() => goToPage(p)}
              style={{
                ...styles.jumpBtn,
                background: pageNum === p ? "var(--accent)" : "var(--bg-hover)",
                color: pageNum === p ? "#fff" : "var(--text-secondary)",
              }}
            >
              p.{p}
            </button>
          ))}
        </div>
      )}

      {/* PDF Document — fileProp is memoized so this never reloads unexpectedly */}
      <Document
        file={fileProp}
        onLoadSuccess={handleLoadSuccess}
        onLoadError={(err) => console.error("PDF load error:", err)}
        loading={<div style={styles.msg}>Loading PDF…</div>}
        error={<div style={styles.msg}>Failed to load PDF.</div>}
      >
        {/* position:relative is CRITICAL — canvas overlay uses position:absolute */}
        <div style={styles.pageWrapper} ref={pageWrapperRef}>
          <Page
            pageNumber={pageNum}
            width={containerWidth > 0 ? containerWidth : undefined}
            renderTextLayer={true}
            renderAnnotationLayer={true}
            onRenderSuccess={handleRenderSuccess}
            loading={<div style={styles.msg}>Rendering page…</div>}
          />
          {pageReady && renderedSize && (
            <HighlightLayer
              fileProp={fileProp}
              pageNum={pageNum}
              query={query}
              renderedSize={renderedSize}
              chunkText={chunkText}
            />
          )}
        </div>
      </Document>

      {/* Pagination — show as soon as numPages is known */}
      {numPages != null && (
        <div style={styles.pagination}>
          <button
            onClick={handlePrev}
            disabled={pageNum <= 1}
            style={{
              ...styles.pageBtn,
              opacity: pageNum <= 1 ? 0.35 : 1,
              cursor: pageNum <= 1 ? "not-allowed" : "pointer",
            }}
          >
            ‹ Prev
          </button>
          <span style={styles.pageInfo}>
            {pageNum} / {numPages}
          </span>
          <button
            onClick={handleNext}
            disabled={pageNum >= numPages}
            style={{
              ...styles.pageBtn,
              opacity: pageNum >= numPages ? 0.35 : 1,
              cursor: pageNum >= numPages ? "not-allowed" : "pointer",
            }}
          >
            Next ›
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Main PDFViewer ───────────────────────────────────────────────────────────
function PDFViewer({ results, query, activePage, activeDocId: activeDocIdProp }) {
  // Group results by doc_id
  const docGroups = useMemo(() => {
    const map = new Map()
    for (const r of results) {
      if (!map.has(r.doc_id)) {
        map.set(r.doc_id, {
          doc_id: r.doc_id,
          filename: r.filename,
          file_url: r.file_url,
          results: [],
        })
      }
      map.get(r.doc_id).results.push(r)
    }
    return Array.from(map.values())
  }, [results])

  const [activeDocId, setActiveDocId] = useState(() => docGroups[0]?.doc_id ?? null)

  // Reset to first doc on new search
  const prevResultsRef = useRef(results)
  if (prevResultsRef.current !== results) {
    prevResultsRef.current = results
    const firstId = docGroups[0]?.doc_id ?? null
    if (firstId !== activeDocId) setActiveDocId(firstId)
  }

  // Sync from parent (result card click)
  useEffect(() => {
    if (activeDocIdProp && activeDocIdProp !== activeDocId) {
      setActiveDocId(activeDocIdProp)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDocIdProp])

  if (!results || results.length === 0) return null

  const activeGroup = docGroups.find((g) => g.doc_id === activeDocId) ?? docGroups[0]

  return (
    <div style={styles.container}>
      {/* Document tabs */}
      {docGroups.length > 1 && (
        <div style={styles.docTabs}>
          {docGroups.map((g) => (
            <button
              key={g.doc_id}
              onClick={() => setActiveDocId(g.doc_id)}
              style={{
                ...styles.docTab,
                borderBottom: g.doc_id === activeDocId
                  ? "2px solid var(--accent)"
                  : "2px solid transparent",
                color: g.doc_id === activeDocId
                  ? "var(--accent)"
                  : "var(--text-muted)",
              }}
              title={g.filename}
            >
              <svg width="11" height="11" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ flexShrink: 0 }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
              <span style={styles.docTabName}>{g.filename}</span>
              <span style={styles.docTabCount}>{g.results.length}</span>
            </button>
          ))}
        </div>
      )}

      {/* Pass the active group's viewer with a stable fileProp */}
      <ActiveViewer
        key={activeGroup.doc_id}
        group={activeGroup}
        query={query}
        activePage={activeGroup.doc_id === activeDocId ? activePage : undefined}
      />
    </div>
  )
}

/**
 * ActiveViewer — wrapper that builds a STABLE memoized fileProp
 * so <Document> never sees a new object reference on re-renders.
 * This is the root cause fix for Prev/Next resetting the page.
 */
function ActiveViewer({ group, query, activePage }) {
  // fileProp is memoized — only changes when the doc_id (URL) actually changes
  const fileProp = useMemo(() => {
    const path = group.file_url || `/api/documents/${group.doc_id}/view`
    let url = path
    if (import.meta.env.VITE_API_URL) {
      const base = import.meta.env.VITE_API_URL.replace(/\/api\/?$/, "")
      url = `${base}${path}`
    }
    const token = localStorage.getItem("token")
    return {
      url,
      httpHeaders: token ? { Authorization: `Bearer ${token}` } : {},
      withCredentials: false,
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group.doc_id]) // only rebuild when the document itself changes

  return (
    <SingleDocViewer
      docResults={group.results}
      query={query}
      activePage={activePage}
      fileProp={fileProp}
    />
  )
}

export default memo(PDFViewer)

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    width: "100%",
    minWidth: 0,
  },
  docTabs: {
    display: "flex",
    gap: 2,
    borderBottom: "1px solid var(--border)",
    marginBottom: 12,
    overflowX: "auto",
    flexShrink: 0,
  },
  docTab: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    padding: "8px 12px",
    background: "transparent",
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 12,
    fontWeight: 500,
    whiteSpace: "nowrap",
    transition: "color 0.15s",
    maxWidth: 180,
  },
  docTabName: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    maxWidth: 120,
  },
  docTabCount: {
    background: "var(--accent-glow)",
    color: "var(--accent-hover)",
    borderRadius: 10,
    padding: "0 5px",
    fontSize: 10,
    fontWeight: 700,
    flexShrink: 0,
  },
  docViewer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
    width: "100%",
    minWidth: 0,
  },
  jumpBar: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
    alignSelf: "flex-start",
    padding: "4px 0",
    width: "100%",
  },
  jumpLabel: {
    fontSize: 11,
    color: "var(--text-muted)",
    fontFamily: "'JetBrains Mono', monospace",
  },
  jumpBtn: {
    border: "none",
    borderRadius: 6,
    padding: "3px 8px",
    fontSize: 11,
    cursor: "pointer",
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: 600,
    transition: "all 0.12s",
  },
  pageWrapper: {
    position: "relative", // CRITICAL for canvas overlay positioning
    width: "100%",
    lineHeight: 0,        // prevents gap below rendered canvas
  },
  msg: {
    color: "var(--text-muted)",
    fontSize: 13,
    padding: 40,
  },
  pagination: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "8px 16px",
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    alignSelf: "center",
  },
  pageBtn: {
    background: "transparent",
    border: "none",
    color: "var(--text-secondary)",
    fontSize: 13,
    fontFamily: "inherit",
    padding: "4px 8px",
    borderRadius: 6,
    transition: "all 0.12s",
  },
  pageInfo: {
    fontSize: 13,
    color: "var(--text-muted)",
    fontFamily: "'JetBrains Mono', monospace",
    minWidth: 60,
    textAlign: "center",
  },
}