import { useEffect, useRef } from "react"
import { pdfjs } from "react-pdf"

/**
 * HighlightLayer — canvas-based highlight overlay.
 *
 * Strategy:
 *  1. Always attempt pdfjs page.getTextContent() for coordinate-based highlights.
 *     This works for text-embedded PDFs perfectly.
 *
 *  2. For image/scanned PDFs pdfjs returns 0 text items (no embedded text layer).
 *     In that case we fall back to checking if the OCR `chunkText` (from search
 *     results, already extracted by pytesseract on the backend) contains the keyword.
 *     If yes, we draw a soft highlight banner across the top of the page so the
 *     user knows this page is a match.
 *
 * Props:
 *   fileProp    — stable { url, httpHeaders } object (memoized in PDFViewer)
 *   pageNum     — 1-based page number currently shown
 *   query       — raw search query string
 *   renderedSize — { width, height } of the rendered PDF canvas in CSS px
 *   chunkText   — OCR/extracted text for this page from search results (fallback)
 */
export default function HighlightLayer({ fileProp, pageNum, query, renderedSize, chunkText }) {
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

    const drawOnCanvas = (drawFn) => {
      const canvas = canvasRef.current
      if (!canvas || cancelled) return
      canvas.width = renderedSize.width
      canvas.height = renderedSize.height
      const ctx = canvas.getContext("2d")
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      drawFn(ctx, canvas.width, canvas.height)
    }

    const run = async () => {
      try {
        // ── Load PDF via pdfjs (browser caches — no re-download) ──────────────
        const loadingTask = pdfjs.getDocument({
          url: fileProp.url,
          httpHeaders: fileProp.httpHeaders || {},
          withCredentials: false,
        })

        const pdfDoc = await loadingTask.promise
        if (cancelled) return

        const page = await pdfDoc.getPage(pageNum)
        if (cancelled) return

        const naturalViewport = page.getViewport({ scale: 1 })
        const scaleX = renderedSize.width / naturalViewport.width
        const scaleY = renderedSize.height / naturalViewport.height

        const textContent = await page.getTextContent()
        if (cancelled) return

        // ── Check if this page has any embedded text items ────────────────────
        const hasEmbeddedText = textContent.items.some(
          (item) => item.str && item.str.trim().length > 0
        )

        if (hasEmbeddedText) {
          // ── STRATEGY 1: coordinate-based highlights (text PDFs) ───────────
          drawOnCanvas((ctx) => {
            ctx.fillStyle = "rgba(251, 191, 36, 0.50)"

            for (const item of textContent.items) {
              const str = item.str
              if (!str || !str.trim()) continue

              const itemClean = str.toLowerCase().replace(/[^a-z0-9\s]/g, " ")
              const itemWords = itemClean.split(/\s+/).filter(Boolean)
              const matched = keywords.some((kw) =>
                itemWords.some((w) => w === kw)
              )
              if (!matched) continue

              // transform = [a, b, c, d, tx, ty]
              // tx,ty = bottom-left origin in PDF coords (Y-axis up)
              const [, , , fontSizePdf, tx, ty] = item.transform

              const itemW = item.width > 0
                ? item.width
                : Math.abs(fontSizePdf) * str.length * 0.55
              const itemH = item.height > 0
                ? item.height
                : Math.abs(fontSizePdf)

              // Flip Y: PDF Y=0 is bottom, canvas Y=0 is top
              const cx = tx * scaleX
              const cy = renderedSize.height - (ty * scaleY) - (itemH * scaleY)
              const cw = itemW * scaleX
              const ch = itemH * scaleY

              const pad = 1
              ctx.fillRect(cx - pad, cy - pad, cw + pad * 2, ch + pad * 2)
            }
          })
        } else {
          // ── STRATEGY 2: image/scanned page — use OCR chunkText fallback ───
          // Check if the OCR text for this page (from search results) contains
          // any of the search keywords.
          const ocrText = (chunkText || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ")
          const ocrWords = new Set(ocrText.split(/\s+/).filter(Boolean))
          const ocrMatch = keywords.some((kw) => ocrWords.has(kw))

          if (ocrMatch) {
            // Draw a labelled banner at the top of the page so user knows
            // the keyword was found by OCR on this scanned page
            drawOnCanvas((ctx, w) => {
              // Semi-transparent amber banner
              ctx.fillStyle = "rgba(251, 191, 36, 0.20)"
              ctx.fillRect(0, 0, w, 36)

              // Left accent bar
              ctx.fillStyle = "rgba(251, 191, 36, 0.85)"
              ctx.fillRect(0, 0, 4, 36)

              // Label text
              ctx.fillStyle = "rgba(120, 80, 0, 0.9)"
              ctx.font = "bold 12px 'Sora', sans-serif"
              ctx.fillText(`Keyword found via OCR: "${keywords.join(", ")}"`, 12, 23)
            })
          }
        }
      } catch (err) {
        if (!cancelled) console.warn("HighlightLayer error:", err)
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
  // fileProp is memoized in PDFViewer so this won't fire on every render
  }, [fileProp, pageNum, query, renderedSize, chunkText])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        borderRadius: 8,
        mixBlendMode: "multiply",
      }}
      aria-hidden="true"
    />
  )
}