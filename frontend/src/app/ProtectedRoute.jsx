import { Navigate, useLocation } from "react-router-dom"
import { useAuthStore } from "../store/authStore"

export function FullPageSpinner() {
  return (
    <div style={styles.page}>
      <span style={styles.spinner} />
    </div>
  )
}

/** Renders children only for a logged-in user; remembers where they were going. */
export default function ProtectedRoute({ children }) {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  if (status === "unknown") return <FullPageSpinner />
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}

/** For /login and /register: a logged-in user is sent to the app instead. */
export function GuestRoute({ children }) {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  if (status === "unknown") return <FullPageSpinner />
  if (status === "authenticated") return <Navigate to={location.state?.from || "/"} replace />
  return children
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-primary)",
  },
  spinner: {
    width: 24,
    height: 24,
    border: "2px solid var(--border-light)",
    borderTopColor: "var(--accent)",
    borderRadius: "50%",
    display: "inline-block",
    animation: "spin 0.8s linear infinite",
  },
}
