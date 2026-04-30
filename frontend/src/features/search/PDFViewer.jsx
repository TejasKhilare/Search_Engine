import { Document, Page, pdfjs } from "react-pdf"
import { useState } from "react"
import HighlightLayer from "./HighlightLayer"

// Use the CDN worker for the current react-pdf version
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`

export default function PDFViewer({ results }) {
  const [numPages, setNumPages] = useState(null)
  const [pageNum, setPageNum] = useState(1)

  if (!results || results.length === 0) {
    return null
  }

  const first = results[0]

  // ✅ FIX: was incorrectly stripping "/api" then re-adding it.
  // With Vite proxy, /api/documents/... works directly.
  // In production with VITE_API_URL set, prepend the base URL without /api suffix.
  const baseUrl = import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL.replace(/\/api\/?$/, "")
    : ""

  const fileUrl = `${baseUrl}/api/documents/${first.doc_id}/view`

  const token = localStorage.getItem("token")

  // Pass auth header so the backend can verify the request
  const httpHeaders = token ? { Authorization: `Bearer ${token}` } : {}

  const currentPage = first.page_no || pageNum

  return (
    <div style={styles.container}>
      <Document
        file={{ url: fileUrl, httpHeaders }}
        onLoadSuccess={({ numPages }) => {
          setNumPages(numPages)
          setPageNum(first.page_no || 1)
        }}
        onLoadError={(err) => console.error("PDF load error:", err)}
        loading={<div style={styles.pdfLoading}>Loading PDF...</div>}
      >
        <Page
          pageNumber={currentPage}
          width={Math.min(600, window.innerWidth - 60)}
          renderTextLayer={true}
          renderAnnotationLayer={true}
        />
        <HighlightLayer results={results} page={currentPage} />
      </Document>

      {numPages && numPages > 1 && (
        <div style={styles.pagination}>
          <button
            onClick={() => setPageNum((p) => Math.max(1, p - 1))}
            disabled={pageNum <= 1}
            style={{ ...styles.pageBtn, opacity: pageNum <= 1 ? 0.4 : 1 }}
          >
            ‹ Prev
          </button>
          <span style={styles.pageInfo}>
            {pageNum} / {numPages}
          </span>
          <button
            onClick={() => setPageNum((p) => Math.min(numPages, p + 1))}
            disabled={pageNum >= numPages}
            style={{ ...styles.pageBtn, opacity: pageNum >= numPages ? 0.4 : 1 }}
          >
            Next ›
          </button>
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 16,
  },
  pdfLoading: {
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
  },
  pageBtn: {
    background: "transparent",
    border: "none",
    color: "var(--text-secondary)",
    fontSize: 13,
    cursor: "pointer",
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