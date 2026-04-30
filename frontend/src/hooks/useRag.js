import { useState } from "react"

export default function useRag() {
  const [answer, setAnswer] = useState("")
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)

  const reset = () => {
    setAnswer("")
    setSources([])
  }

  return {
    answer,
    setAnswer,
    sources,
    setSources,
    loading,
    setLoading,
    reset,
  }
}