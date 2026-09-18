import { useCallback } from "react"
import { useAuthStore } from "../store/authStore"
import { refreshSession } from "../shared/utils/axios"
import { loginUser, logoutUser, registerUser } from "../features/auth/api"
import { useDocumentStore } from "../store/documentStore"

/**
 * Restores a session on app start. Access tokens are short-lived and the CSRF
 * token is only kept in memory, so a refresh both validates the session and
 * re-issues everything the page needs after a reload.
 */
export async function bootstrapSession() {
  try {
    await refreshSession()
  } catch {
    // No valid session: status is now "anonymous"
  }
}

export default function useAuth() {
  const { status, user, setSession, clearSession } = useAuthStore()

  const login = useCallback(
    async (email, password) => {
      setSession(await loginUser({ email, password }))
    },
    [setSession]
  )

  const register = useCallback(
    async ({ username, email, password }) => {
      await registerUser({ username, email, password })
      setSession(await loginUser({ email, password }))
    },
    [setSession]
  )

  const logout = useCallback(async () => {
    try {
      await logoutUser()
    } finally {
      // Clear local state even if the network call failed
      clearSession()
      useDocumentStore.getState().reset()
    }
  }, [clearSession])

  return { status, user, isAuthenticated: status === "authenticated", login, register, logout }
}
