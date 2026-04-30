import { BrowserRouter, Routes, Route } from "react-router-dom"
import SearchPage from "../features/search/SearchPage"
import AiSearchPage from "../features/rag/AiSearchPage"
import LoginPage from "../features/auth/LoginPage"
import ProtectedRoute from "./ProtectedRoute"

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

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
      </Routes>
    </BrowserRouter>
  )
}