import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import SearchPage from "../features/search/SearchPage"
import AiSearchPage from "../features/rag/AiSearchPage"
import LoginPage from "../features/auth/LoginPage"
import RegisterPage from "../features/auth/RegisterPage"
import ProtectedRoute, { GuestRoute } from "./ProtectedRoute"

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
        <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <SearchPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/ai"
          element={
            <ProtectedRoute>
              <AiSearchPage />
            </ProtectedRoute>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
