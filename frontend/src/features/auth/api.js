import api from "../../shared/utils/axios"

export const loginUser = async (data) => {
  const res = await api.post("/login", data)
  return res.data
}

export const registerUser = async (data) => {
  const res = await api.post("/register", data)
  return res.data
}

export const logoutUser = () => {
  localStorage.removeItem("token")
}