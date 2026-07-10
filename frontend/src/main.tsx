import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { MotionConfig } from "motion/react";
// Self-hosted fonts (no external requests — Docker-friendly).
import "@fontsource-variable/bricolage-grotesque"; // display
import "@fontsource-variable/geist"; // body
import "@fontsource/jetbrains-mono/400.css"; // code
import "@fontsource/jetbrains-mono/500.css";
import "./i18n";
import "./index.css";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { ThemeProvider } from "./theme/ThemeContext";
import { ToastProvider } from "./components/Toast";
import { queryClient } from "./lib/queryClient";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* reducedMotion="user" makes every Motion animation (incl. transform-based
        reveals the CSS reset can't reach) honour the OS setting, app-wide. */}
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <AuthProvider>
              <ToastProvider>
                <App />
              </ToastProvider>
            </AuthProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
);
