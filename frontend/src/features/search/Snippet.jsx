/**
 * Renders a search snippet with its highlight ranges. Highlights are character
 * offsets from the API (never HTML), so document text can't inject markup.
 */
export default function Snippet({ snippet, style }) {
  if (!snippet) return null
  const { text, highlights = [] } = snippet

  const parts = []
  let cursor = 0
  for (const [start, end] of highlights) {
    if (start < cursor) continue // ignore overlaps
    if (start > cursor) parts.push(text.slice(cursor, start))
    parts.push(
      <mark key={start} className="hl">
        {text.slice(start, end)}
      </mark>
    )
    cursor = end
  }
  if (cursor < text.length) parts.push(text.slice(cursor))

  return <p style={style}>{parts}</p>
}
