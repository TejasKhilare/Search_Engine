import { useEffect } from "react"
import AppRoutes from "./routes"
import { bootstrapSession } from "../hooks/useAuth"

export default function App() {
  useEffect(() => {
    bootstrapSession()
  }, [])

  return <AppRoutes />
}
