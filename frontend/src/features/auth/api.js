import api from "../../shared/utils/axios"

export const loginUser = async (data) => {
  const res = await api.post("/login", data)
  return res.data
}