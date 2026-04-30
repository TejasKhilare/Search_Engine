// Lightweight in-memory toast system — no extra library needed
// Usage: import { toast } from "../shared/utils/toast"
//        toast.success("Uploaded!") | toast.error("Failed") | toast.info("...")

const container = (() => {
  let el = null
  return () => {
    if (!el) {
      el = document.createElement("div")
      el.className = "toast-container"
      document.body.appendChild(el)
    }
    return el
  }
})()

function show(message, type = "info", duration = 3500) {
  const c = container()
  const toast = document.createElement("div")
  toast.className = `toast toast-${type}`
  toast.textContent = message
  c.appendChild(toast)

  setTimeout(() => {
    toast.style.opacity = "0"
    toast.style.transform = "translateY(8px)"
    toast.style.transition = "opacity 0.2s ease, transform 0.2s ease"
    setTimeout(() => toast.remove(), 220)
  }, duration)
}

export const toast = {
  success: (msg) => show(msg, "success"),
  error: (msg) => show(msg, "error"),
  info: (msg) => show(msg, "info"),
}