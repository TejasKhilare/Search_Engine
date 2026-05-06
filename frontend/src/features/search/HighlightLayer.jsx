import { useEffect, useRef } from "react"
import { pdfjs } from "react-pdf"

/**
 * HighlightLayer — canvas-based highlight overlay.
 *
 * Works for BOTH text-based AND image/scanned PDFs because it uses
 * pdfjs page.getTextContent() to get word bounding boxes, then draws
 * semi-transparent rectangles on a <canvas> positioned exactly over
 * the rendered PDF page.
 *
 * For scanned PDFs the backend already ran OCR (pytesseract) and stored
 * the text. However react-pdf's text layer may still be absent. This
 * approach uses pdfjs directly to read whatever text is embedded
 * (including OCR-injected invisible text layers if present).
 *
 * Props:
 *   fileProp     — { url, httpHeaders } same object PDFViewer passes to <Document>
 *   pageNum      — 1-based page number currently shown
 *   query        — raw search query string
 *   renderedSize — { width, height } of the rendered PDF canvas in CSS pixels
 */
export default function HighlightLayer({ fileProp, pageNum, query, renderedSize }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!query || !fileProp?.url || !renderedSize?.width || !renderedSize?.height) return

    // ── Build keyword set from query only ─────────────────────────────────────
    const stopWords = new Set([
      "the","a","an","is","are","was","were","be","been","being",
      "have","has","had","do","does","did","will","would","could",
      "should","may","might","shall","can","need","dare","ought",
      "used","to","of","in","on","at","by","for","with","about",
      "as","into","through","during","before","after","above","below",
      "from","up","down","out","off","over","under","again","and",
      "but","or","nor","so","yet","both","either","neither","not",
      "no","its","it","this","that","these","those","i","you","he",
      "she","we","they","what","which","who","whom","how","all",
      "each","few","more","most","other","some","such","than","too",
      "very","just","also",
    ])

    const keywords = query
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 1 && !stopWords.has(w))

    if (keywords.length === 0) return

    let cancelled = false

    const run = async () => {
      try {
        // Load PDF via pdfjs — browser caches it so no re-download
        const loadingTask = pdfjs.getDocument({
          url: fileProp.url,
          httpHeaders: fileProp.httpHeaders || {},
          withCredentials: false,
        })

        const pdfDoc = await loadingTask.promise
        if (cancelled) return

        const page = await pdfDoc.getPage(pageNum)
        if (cancelled) return

        // Natural viewport at scale=1 gives us PDF unit dimensions
        const naturalViewport = page.getViewport({ scale: 1 })

        // Scale factors: how many CSS pixels per PDF unit
        const scaleX = renderedSize.width / naturalViewport.width
        const scaleY = renderedSize.height / naturalViewport.height

        // Get text content — works for embedded text AND OCR text layers
        const textContent = await page.getTextContent()
        if (cancelled) return

        const canvas = canvasRef.current
        if (!canvas) return

        // Match canvas resolution to rendered size
        canvas.width = renderedSize.width
        canvas.height = renderedSize.height

        const ctx = canvas.getContext("2d")
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.fillStyle = "rgba(251, 191, 36, 0.50)"

        for (const item of textContent.items) {
          const str = item.str
          if (!str || !str.trim()) continue

          // Whole-word keyword match (case-insensitive)
          const itemClean = str.toLowerCase().replace(/[^a-z0-9\s]/g, " ")
          const itemWords = itemClean.split(/\s+/).filter(Boolean)
          const matched = keywords.some((kw) =>
            itemWords.some((w) => w === kw)
          )
          if (!matched) continue

          // item.transform = [a, b, c, d, tx, ty]
          // tx, ty = bottom-left origin in PDF coordinate space (Y axis up)
          const [, , , fontSizePdf, tx, ty] = item.transform

          const itemW = item.width > 0 ? item.width : Math.abs(fontSizePdf) * str.length * 0.55
          const itemH = item.height > 0 ? item.height : Math.abs(fontSizePdf)

          // Convert PDF coords to canvas coords
          // PDF Y=0 is at bottom; canvas Y=0 is at top → flip
          const cx = tx * scaleX
          const cy = renderedSize.height - (ty * scaleY) - (itemH * scaleY)
          const cw = itemW * scaleX
          const ch = itemH * scaleY

          const pad = 1
          ctx.fillRect(cx - pad, cy - pad, cw + pad * 2, ch + pad * 2)
        }
      } catch (err) {
        if (!cancelled) console.warn("HighlightLayer:", err)
      }
    }

    run()

    return () => {
      cancelled = true
      const canvas = canvasRef.current
      if (canvas) {
        const ctx = canvas.getContext("2d")
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  }, [fileProp, pageNum, query, renderedSize])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        // Use 100% so it scales with the responsive container
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        borderRadius: 8,
        // multiply blend: highlight blends with PDF content underneath
        mixBlendMode: "multiply",
      }}
      aria-hidden="true"
    />
  )
}