import api from "../../shared/utils/axios"

export const aiSearch = async (query) => {
  const res = await api.post("/ai-search", {
    query,
    top_k: 5,
  })

  return res.data
}