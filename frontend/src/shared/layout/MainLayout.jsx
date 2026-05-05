import { useState, useEffect } from "react"
import Navbar from "../components/Navbar"

export default function MainLayout({ sidebar, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768)
    check()
    window.addEventListener("resize", check)
    return () => window.removeEventListener("resize", check)
  }, [])

  // Close sidebar when clicking outside on mobile
  const handleOverlayClick = () => setSidebarOpen(false)

  return (
    <div style={styles.root}>
      <Navbar
        onMenuClick={() => setSidebarOpen((v) => !v)}
        showMenu={isMobile && !!sidebar}
      />
      <div style={styles.body}>
        {/* Sidebar — on desktop always visible, on mobile slides in as overlay */}
        {sidebar && (
          <>
            {/* Mobile overlay backdrop */}
            {isMobile && sidebarOpen && (
              <div
                style={styles.overlay}
                onClick={handleOverlayClick}
              />
            )}
            <aside
              style={{
                ...styles.sidebar,
                ...(isMobile ? {
                  position: "fixed",
                  top: 56, // navbar height
                  left: 0,
                  height: "calc(100vh - 56px)",
                  zIndex: 200,
                  transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
                  transition: "transform 0.25s ease",
                } : {}),
              }}
            >
              {sidebar}
            </aside>
          </>
        )}
        <main style={styles.main}>{children}</main>
      </div>
    </div>
  )
}

const styles = {
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    overflow: "hidden",
    background: "var(--bg-primary)",
  },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
    position: "relative",
  },
  sidebar: {
    width: "var(--sidebar-w)",
    flexShrink: 0,
    borderRight: "1px solid var(--border)",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    background: "var(--bg-secondary)",
  },
  overlay: {
    position: "fixed",
    inset: 0,
    top: 56,
    background: "rgba(0,0,0,0.5)",
    zIndex: 199,
  },
  main: {
    flex: 1,
    overflow: "auto",
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
}