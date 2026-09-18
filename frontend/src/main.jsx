import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import "./index.css"

import App from "./app/App"

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
)
