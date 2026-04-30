import { useState } from "react"

export default function SearchBar({ onSearch }) {
  const [input, setInput] = useState("")

  return (
    <div className="mb-4 flex gap-2">
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        className="border p-2 flex-1"
        placeholder="Search..."
      />

      <button
        onClick={() => onSearch(input)}
        className="bg-blue-500 text-white px-4"
      >
        Search
      </button>
    </div>
  )
}