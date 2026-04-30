import { useEffect } from "react"

export default function HighlightLayer({ results, page }) {
  useEffect(() => {
    const spans = document.querySelectorAll(".react-pdf__Page__textContent span")

    // RESET FIRST
    spans.forEach((span) => {
      span.style.background = "transparent"
    })

    spans.forEach((span) => {
      const text = span.textContent.toLowerCase()

      const match = results.find(
        (r) =>
          r.page_no === page &&
          text.includes(r.content.slice(0, 20).toLowerCase())
      )

      if (match) {
        span.style.background = "yellow"
      }
    })
  }, [results, page])

  return null
}