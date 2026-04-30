import { uploadDocument, getDocumentStatus, fetchDocuments } from "./api"
import { useDocumentStore } from "../../store/documentStore"

export default function UploadButton() {
  const { setDocuments, updateDocumentStatus } = useDocumentStore()

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    try {
      const res = await uploadDocument(file)
      const docId = res.doc_id

      // Add immediately
      setDocuments((prev) => [
        ...prev,
        {
          doc_id: docId,
          filename: file.name,
          status: "processing",
        },
      ])

      const interval = setInterval(async () => {
        const statusRes = await getDocumentStatus(docId)

        updateDocumentStatus(docId, statusRes.status)

        if (["completed", "failed"].includes(statusRes.status)) {
          clearInterval(interval)

          const updatedDocs = await fetchDocuments()
          setDocuments(updatedDocs)
        }
      }, 2000)
    } catch {
      alert("Upload failed")
    }
  }

  return <input type="file" onChange={handleUpload} />
}