import { Document, Page, pdfjs } from "react-pdf"
import { useState } from "react"
import HighlightLayer from "./HighlightLayer"

pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`

export default function PDFViewer({ results }) {
  const [numPages, setNumPages] = useState(null)

  if (!results.length) return <div>No results</div>

  const first = results[0]

  const fileUrl = `${import.meta.env.VITE_API_URL.replace("/api", "")}/api/documents/${first.doc_id}/view`

  return (
    <div>
      <Document file={fileUrl} onLoadSuccess={({ numPages }) => setNumPages(numPages)}>
        <Page pageNumber={first.page_no} />

        <HighlightLayer results={results} page={first.page_no} />
      </Document>
    </div>
  )
}