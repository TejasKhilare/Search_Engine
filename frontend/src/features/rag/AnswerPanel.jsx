export default function AnswerPanel({ answer, sources, loading }) {
  if (loading) {
    return <div>Thinking...</div>
  }

  if (!answer) {
    return <div>No answer yet</div>
  }

  return (
    <div>
      <div className="p-4 border rounded bg-gray-50">
        <h2 className="text-lg font-semibold mb-2">Answer</h2>
        <p className="text-gray-800 whitespace-pre-line">{answer}</p>
      </div>

      <div className="mt-4">
        <h3 className="font-semibold mb-2">Sources</h3>

        {sources.map((s, i) => (
          <div key={i} className="border p-2 mb-2 rounded">
            <div className="text-sm text-gray-600">
              Doc: {s.doc_id} | Page: {s.page_no}
            </div>

            <div className="text-sm mt-1">
              {s.content.slice(0, 150)}...
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}