import { useNavigate, useLocation, Link } from "react-router-dom"
import { logoutUser } from "../../features/auth/api"
import { toast } from "../utils/toast"

export default function Navbar({ onMenuClick, showMenu }) {
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logoutUser()
    toast.info("Signed out")
    navigate("/login")
  }

  const isActive = (path) => location.pathname === path

  return (
    <nav style={styles.nav}>
      {/* Hamburger — only on mobile when sidebar exists */}
      {showMenu && (
        <button onClick={onMenuClick} style={styles.menuBtn} aria-label="Toggle sidebar">
          <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
      )}

      {/* Brand */}
      <div style={styles.brand}>
        <svg width="22" height="21" viewBox="0 0 48 46" fill="none">
          <path fill="#7c6af7" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/>
        </svg>
        <span style={styles.brandText}>DocSearch</span>
      </div>

      {/* Nav links */}
      <div style={styles.links}>
        <Link
          to="/"
          style={{
            ...styles.link,
            ...(isActive("/") ? styles.linkActive : {}),
          }}
        >
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607z" />
          </svg>
          <span style={styles.linkText}>Search</span>
        </Link>

        <Link
          to="/ai"
          style={{
            ...styles.link,
            ...(isActive("/ai") ? styles.linkActive : {}),
          }}
        >
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
          </svg>
          <span style={styles.linkText}>AI Ask</span>
        </Link>
      </div>

      {/* Logout */}
      <button onClick={handleLogout} style={styles.logoutBtn}>
        <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75" />
        </svg>
        <span style={styles.logoutText}>Sign out</span>
      </button>
    </nav>
  )
}

const styles = {
  nav: {
    height: 56,
    background: "var(--bg-secondary)",
    borderBottom: "1px solid var(--border)",
    display: "flex",
    alignItems: "center",
    padding: "0 16px",
    gap: 8,
    flexShrink: 0,
  },
  menuBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 36,
    height: 36,
    background: "transparent",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    color: "var(--text-secondary)",
    flexShrink: 0,
    padding: 0,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginRight: "auto",
  },
  brandText: {
    fontSize: 15,
    fontWeight: 700,
    color: "var(--text-primary)",
    letterSpacing: "-0.02em",
  },
  links: {
    display: "flex",
    gap: 4,
  },
  link: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 10px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    textDecoration: "none",
    transition: "all 0.15s",
    letterSpacing: "0.01em",
  },
  linkText: {
    // Hidden on very small screens via CSS — link icons still show
  },
  linkActive: {
    background: "var(--accent-glow)",
    color: "var(--accent-hover)",
  },
  logoutBtn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 10px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    background: "transparent",
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "all 0.15s",
    flexShrink: 0,
  },
  logoutText: {},
}