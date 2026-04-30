import { useState } from "react"

export default function useSearch() {
  const [results, setResults] = useState([])
  const [activeDoc, setActiveDoc] = useState(null)
  const [activePage, setActivePage] = useState(null)
  const [query, setQuery] = useState("")

  const resetSearch = () => {
    setResults([])
    setActiveDoc(null)
    setActivePage(null)
  }

  return {
    results,
    setResults,
    activeDoc,
    setActiveDoc,
    activePage,
    setActivePage,
    query,
    setQuery,
    resetSearch,
  }
}