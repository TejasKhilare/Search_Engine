import api from "../../shared/utils/axios"

export const fetchDocuments = async () => {
  const res = await api.get("/documents")
  return res.data
}

export const uploadDocument = async (file) => {
  const formData = new FormData()
  formData.append("file", file)

  const res = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  })

  return res.data
}

export const deleteDocument = async (docId) => {
  const res = await api.delete(`/documents/${docId}`)
  return res.data
}

export const getDocumentStatus = async (docId) => {
  const res = await api.get(`/document/${docId}/status`)
  return res.data
}