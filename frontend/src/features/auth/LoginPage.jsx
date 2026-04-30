import { useState } from "react"
import { loginUser } from "./api"
import { useNavigate } from "react-router-dom"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const navigate = useNavigate()

  const handleLogin = async () => {
    try {
      const res = await loginUser({ email, password })

      localStorage.setItem("token", res.access_token)

      navigate("/")
    } catch {
      alert("Invalid credentials")
    }
  }

  return (
    <div className="flex justify-center items-center h-screen">
      <div className="p-6 border rounded w-80">
        <h2 className="text-xl mb-4">Login</h2>

        <input
          className="border p-2 w-full mb-2"
          placeholder="Email"
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          type="password"
          className="border p-2 w-full mb-2"
          placeholder="Password"
          onChange={(e) => setPassword(e.target.value)}
        />

        <button
          onClick={handleLogin}
          className="bg-blue-500 text-white px-4 py-2 w-full"
        >
          Login
        </button>
      </div>
    </div>
  )
}