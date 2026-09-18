import axios from "axios"
import { useAuthStore } from "../../store/authStore"

// Dev: calls /api/v1 on the Vite server, which proxies to the backend (same origin).
// Prod: set VITE_API_URL to the backend origin, e.g. https://api.example.com
export const API_BASE = `${import.meta.env.VITE_API_URL || ""}/api/v1`

const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"])
// Auth endpoints never trigger the refresh-and-retry flow (avoids loops)
const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout", "/auth/token"]

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // send the HttpOnly auth cookies
})

function readCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

export function csrfToken() {
  // In memory after login/refresh; the readable cookie covers same-site setups
  return useAuthStore.getState().csrfToken || readCookie("csrf_token")
}

api.interceptors.request.use((config) => {
  if (UNSAFE_METHODS.has((config.method || "get").toLowerCase())) {
    const token = csrfToken()
    if (token) config.headers["X-CSRF-Token"] = token
  }
  return config
})

// ── Session refresh ──────────────────────────────────────────────────────────
// Concurrent 401s share ONE refresh request: refresh tokens are single-use, so
// parallel refreshes would look like token theft to the server.
let refreshInFlight = null

export function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = api
      .post("/auth/refresh")
      .then((res) => {
        useAuthStore.getState().setSession(res.data)
        return res.data
      })
      .catch((err) => {
        useAuthStore.getState().clearSession()
        throw err
      })
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    const isAuthCall = NO_REFRESH.some((path) => original?.url?.startsWith(path))

    if (status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true
      try {
        await refreshSession()
        return api(original) // retry with the new access cookie (and CSRF token)
      } catch {
        // Session is gone; ProtectedRoute redirects to /login on the status change
      }
    }
    return Promise.reject(error)
  }
)

/** Human-readable message from the API's error envelope. */
export function getErrorMessage(error, fallback = "Something went wrong") {
  const body = error?.response?.data?.error
  if (!body) {
    if (error?.response?.status === 429) return "Too many requests. Please wait a moment."
    return error?.message === "Network Error" ? "Cannot reach the server" : fallback
  }
  if (body.code === "validation_error" && Array.isArray(body.details) && body.details.length) {
    const first = body.details[0]
    return first.field ? `${first.field}: ${first.message}` : first.message
  }
  return body.message || fallback
}

export default api
