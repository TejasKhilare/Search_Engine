import api from "../../shared/utils/axios"

/** Returns { user, csrf_token, access_token_expires_at }; tokens are set as cookies. */
export const loginUser = async ({ email, password }) => {
  const res = await api.post("/auth/login", { email, password })
  return res.data
}

export const registerUser = async ({ username, email, password }) => {
  const res = await api.post("/auth/register", { username, email, password })
  return res.data
}

export const logoutUser = async () => {
  await api.post("/auth/logout")
}
