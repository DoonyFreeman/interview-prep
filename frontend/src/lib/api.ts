import axios from "axios";
import { clearToken, getToken } from "./token";

const baseURL = `${import.meta.env.VITE_API_BASE ?? "http://localhost:8000"}/api`;

export const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // On an expired/invalid token, drop it and bounce to login.
    if (error?.response?.status === 401 && getToken()) {
      clearToken();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

/** Extract a human-readable message from an axios error. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}
