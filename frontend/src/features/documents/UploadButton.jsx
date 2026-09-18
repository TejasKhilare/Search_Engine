import { useRef, useState } from "react"
import { MAX_UPLOAD_MB, uploadDocument } from "./api"
import { useDocumentStore } from "../../store/documentStore"
import { getErrorMessage } from "../../shared/utils/axios"
import { toast } from "../../shared/utils/toast"

export default function UploadButton() {
  const upsertDocument = useDocumentStore((s) => s.upsertDocument)
  const inputRef = useRef(null)
  const [progress, setProgress] = useState(null) // null = idle, 0–100 while uploading
  const uploading = progress !== null

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = "" // allow picking the same file again
    if (!file) return

    // Fast feedback; the server re-validates the actual content
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF files are supported")
      return
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      toast.error(`File is larger than ${MAX_UPLOAD_MB} MB`)
      return
    }

    setProgress(0)
    try {
      const doc = await uploadDocument(file, setProgress)
      upsertDocument(doc) // status "pending": the list's poller tracks it from here
      toast.info(`Processing ${doc.filename}…`)
    } catch (err) {
      const body = err.response?.data?.error
      if (err.response?.status === 409 && body?.details?.filename) {
        toast.info(`Already uploaded as "${body.details.filename}"`)
      } else {
        toast.error(getErrorMessage(err, "Upload failed"))
      }
    } finally {
      setProgress(null)
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
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
            {progress < 100 ? `Uploading… ${progress}%` : "Validating…"}
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