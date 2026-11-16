import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Aplica o último tema antes do primeiro quadro para evitar um flash claro.
try {
  const tema = window.localStorage.getItem("prancha-tema");
  if (tema === "claro" || tema === "escuro") {
    document.documentElement.dataset.tema = tema;
  }
} catch {
  // Sem armazenamento local: o tema salvo é aplicado quando o motor conectar.
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
