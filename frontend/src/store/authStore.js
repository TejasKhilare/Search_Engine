import { create } from "zustand"

// Session state. Tokens themselves live in HttpOnly cookies the browser manages;
// JS only ever holds the user profile and the CSRF token.
//   status: "unknown"       → still checking for an existing session (app start)
//           "authenticated" → logged in
//           "anonymous"     → not logged in
export const useAuthStore = create((set) => ({
  status: "unknown",
  user: null,
  csrfToken: null,

  setSession: ({ user, csrf_token }) =>
    set({ status: "authenticated", user, csrfToken: csrf_token }),

  clearSession: () => set({ status: "anonymous", user: null, csrfToken: null }),
}))
