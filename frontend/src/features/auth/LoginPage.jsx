import { useState } from "react"
import { loginUser } from "./api"
import { useNavigate, Link } from "react-router-dom"
import { toast } from "../../shared/utils/toast"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      toast.error("Please fill in all fields")
      return
    }

    setLoading(true)
    try {
      const res = await loginUser({ email, password })
      localStorage.setItem("token", res.access_token)
      toast.success("Welcome back!")
      navigate("/")
    } catch (err) {
      const msg = err.response?.data?.detail || "Invalid credentials"
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleLogin()
  }

  return (
    <div style={styles.page}>
      {/* Background orb */}
      <div style={styles.orb} />

      <div style={styles.card}>
        {/* Logo */}
        <div style={styles.logo}>
          <svg width="32" height="32" viewBox="0 0 48 46" fill="none">
            <path fill="#7c6af7" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/>
          </svg>
          <span style={styles.logoText}>DocSearch</span>
        </div>

        <h1 style={styles.heading}>Sign in</h1>
        <p style={styles.subheading}>Access your document intelligence workspace</p>

        <div style={styles.form}>
          <div style={styles.field}>
            <label style={styles.label}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="you@example.com"
              style={styles.input}
              autoComplete="email"
              autoFocus
            />
          </div>

          <div style={styles.field}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="••••••••"
              style={styles.input}
              autoComplete="current-password"
            />
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            style={{
              ...styles.btn,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? (
              <span style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
                <span style={styles.spinner} />
                Signing in...
              </span>
            ) : (
              "Sign in"
            )}
          </button>
        </div>

        <p style={styles.footer}>
          Don&apos;t have an account?{" "}
          <Link to="/register" style={styles.link}>
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-primary)",
    position: "relative",
    overflow: "hidden",
  },
  orb: {
    position: "absolute",
    width: 500,
    height: 500,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(124,106,247,0.15) 0%, transparent 70%)",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    pointerEvents: "none",
  },
  card: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: 20,
    padding: "40px 44px",
    width: "100%",
    maxWidth: 420,
    position: "relative",
    boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
  },
  logo: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 28,
  },
  logoText: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text-primary)",
    letterSpacing: "-0.02em",
  },
  heading: {
    fontSize: 26,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: "0 0 6px",
    letterSpacing: "-0.03em",
  },
  subheading: {
    fontSize: 14,
    color: "var(--text-secondary)",
    margin: "0 0 28px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    letterSpacing: "0.01em",
  },
  input: {
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "11px 14px",
    fontSize: 14,
    color: "var(--text-primary)",
    outline: "none",
    transition: "border-color 0.15s",
    fontFamily: "inherit",
  },
  btn: {
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: 10,
    padding: "12px 0",
    fontSize: 14,
    fontWeight: 600,
    width: "100%",
    marginTop: 4,
    fontFamily: "inherit",
    transition: "background 0.15s, transform 0.1s",
    letterSpacing: "0.01em",
  },
  spinner: {
    width: 14,
    height: 14,
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    display: "inline-block",
    animation: "spin 0.8s linear infinite",
  },
  footer: {
    marginTop: 24,
    fontSize: 13,
    color: "var(--text-secondary)",
    textAlign: "center",
  },
  link: {
    color: "var(--accent-hover)",
    textDecoration: "none",
    fontWeight: 500,
  },
}