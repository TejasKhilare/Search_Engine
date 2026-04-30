import Sidebar from "../documents/Sidebar"
import SearchBar from "./SearchBar"
import PDFViewer from "./PDFViewer"
import useSearch from "../../hooks/useSearch"
import { searchDocuments } from "./api"

export default function SearchPage() {
  const {
    results,
    setResults,
    setActiveDoc,
    setActivePage,
    resetSearch,
  } = useSearch()

  const handleSearch = async (query) => {
    resetSearch()

    try {
      const data = await searchDocuments(query)

      setResults(data.results)

      if (data.results.length > 0) {
        const top = data.results[0]

        setActiveDoc(top.doc_id)
        setActivePage(top.page_no)
      }
    } catch {
      alert("Search failed")
    }
  }

  return (
    <div className="flex">
      <Sidebar />

      <div className="flex-1 p-6">
        <SearchBar onSearch={handleSearch} />

        <PDFViewer results={results} />
      </div>
    </div>
  )
}