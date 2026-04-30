import Sidebar from "../documents/Sidebar"
import { useState } from "react"
import { aiSearch } from "./api"
import useRag from "../../hooks/useRag"
import AnswerPanel from "./AnswerPanel"

export default function AiSearchPage() {
  const [query, setQuery] = useState("")
  const { answer, setAnswer, sources, setSources, loading, setLoading, reset } =
    useRag()

  const handleSearch = async () => {
    if (!query.trim()) return

    reset()
    setLoading(true)

    try {
      const res = await aiSearch(query)

      setAnswer(res.answer)
      setSources(res.sources)
    } catch {
      alert("AI search failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex">
      <Sidebar />

      <div className="flex-1 p-6">
        <div className="flex gap-2 mb-4">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="border p-2 flex-1"
            placeholder="Ask anything..."
          />

          <button
            onClick={handleSearch}
            className="bg-purple-500 text-white px-4"
          >
            Ask
          </button>
        </div>

        <AnswerPanel
          answer={answer}
          sources={sources}
          loading={loading}
        />
      </div>
    </div>
  )
}