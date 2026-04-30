import { useEffect } from "react"
import { fetchDocuments, deleteDocument } from "./api"
import { useDocumentStore } from "../../store/documentStore"

export default function DocumentList() {
  const {
    documents,
    setDocuments,
    setSelectedDoc,
    removeDocument,
  } = useDocumentStore()

  useEffect(() => {
    const loadDocs = async () => {
      try {
        const data = await fetchDocuments()
        setDocuments(data)
      } catch (err) {
        console.error("Failed to load documents")
      }
    }

    loadDocs()
  }, [])

  const handleDelete = async (docId) => {
    try {
      await deleteDocument(docId)
      removeDocument(docId)
    } catch {
      alert("Delete failed")
    }
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div
          key={doc.doc_id}
          className="p-2 border rounded flex justify-between items-center cursor-pointer hover:bg-gray-200"
          onClick={() => setSelectedDoc(doc)}
        >
          <div>
            <div className="text-sm font-medium">{doc.filename}</div>
            <div className="text-xs text-gray-500">{doc.status}</div>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation()
              handleDelete(doc.doc_id)
            }}
            className="text-red-500 text-sm"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}