import Navbar from "../components/Navbar"

export default function MainLayout({ sidebar, children }) {
  return (
    <div style={styles.root}>
      <Navbar />
      <div style={styles.body}>
        {sidebar && <aside style={styles.sidebar}>{sidebar}</aside>}
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
  },
  sidebar: {
    width: "var(--sidebar-w)",
    flexShrink: 0,
    borderRight: "1px solid var(--border)",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  main: {
    flex: 1,
    overflow: "auto",
    display: "flex",
    flexDirection: "column",
  },
}