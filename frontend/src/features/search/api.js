import api from "../../shared/utils/axios"

export const searchDocuments = async (query) => {
  const res = await api.get("/search", {
    params: { q: query }
  })
  return res.data
}