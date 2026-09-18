import api, { API_BASE } from "../../shared/utils/axios"

export const MAX_UPLOAD_MB = 10

/** Returns a page: { items, total, limit, offset } — newest first. */
export const fetchDocuments = async ({ limit = 50, offset = 0 } = {}) => {
  const res = await api.get("/documents", { params: { limit, offset } })
  return res.data
}

export const getDocument = async (id) => {
  const res = await api.get(`/documents/${id}`)
  return res.data
}

export const uploadDocument = async (file, onProgress) => {
  const formData = new FormData()
  formData.append("file", file)
  // No explicit Content-Type: the browser adds the multipart boundary itself
  const res = await api.post("/documents", formData, {
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  })
  return res.data
}

export const deleteDocument = async (id) => {
  await api.delete(`/documents/${id}`)
}

export const reprocessDocument = async (id) => {
  const res = await api.post(`/documents/${id}/reprocess`)
  return res.data
}

/** Streamed through the API with the session cookie; supports Range requests. */
export const documentFileUrl = (id) => `${API_BASE}/documents/${id}/file`
