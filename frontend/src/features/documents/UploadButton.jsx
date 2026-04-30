import { useRef, useState } from "react"
import { uploadDocument, getDocumentStatus, fetchDocuments } from "./api"
import { useDocumentStore } from "../../store/documentStore"
import { toast } from "../../shared/utils/toast"

export default function UploadButton() {
  const { setDocuments, updateDocumentStatus } = useDocumentStore()
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Reset input so same file can be re-uploaded
    e.target.value = ""

    setUploading(true)

    try {
      const res = await uploadDocument(file)
      const docId = res.doc_id

      toast.info(`Uploading ${file.name}...`)

      // Add optimistically
      const currentDocs = useDocumentStore.getState().documents
      setDocuments([
        { doc_id: docId, filename: file.name, status: "processing", total_chunks: 0 },
        ...currentDocs,
      ])

      // Poll for completion
      const interval = setInterval(async () => {
        try {
          const statusRes = await getDocumentStatus(docId)
          updateDocumentStatus(docId, statusRes.status)

          if (statusRes.status === "completed") {
            clearInterval(interval)
            toast.success(`${file.name} processed successfully`)
            const updatedDocs = await fetchDocuments()
            setDocuments(updatedDocs)
          } else if (statusRes.status === "failed") {
            clearInterval(interval)
            toast.error(`Processing failed for ${file.name}`)
          }
        } catch {
          clearInterval(interval)
        }
      }, 2000)
    } catch (err) {
      const msg = err.response?.data?.detail || "Upload failed"
      toast.error(msg)
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        onChange={handleUpload}
        style={{ display: "none" }}
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        style={{
          ...styles.btn,
          opacity: uploading ? 0.7 : 1,
          cursor: uploading ? "not-allowed" : "pointer",
        }}
      >
        {uploading ? (
          <>
            <span style={styles.spinner} />
            Uploading...
          </>
        ) : (
          <>
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z" />
            </svg>
            Upload PDF
          </>
        )}
      </button>
    </>
  )
}

const styles = {
  btn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    width: "100%",
    padding: "9px 0",
    background: "var(--accent-glow)",
    border: "1px dashed rgba(124,106,247,0.4)",
    borderRadius: 10,
    color: "var(--accent-hover)",
    fontSize: 13,
    fontWeight: 600,
    fontFamily: "inherit",
    transition: "all 0.15s",
    letterSpacing: "0.01em",
  },
  spinner: {
    width: 12,
    height: 12,
    border: "2px solid rgba(149,133,255,0.3)",
    borderTopColor: "var(--accent-hover)",
    borderRadius: "50%",
    display: "inline-block",
    animation: "spin 0.8s linear infinite",
  },
}