import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { clearToken, getToken, setToken, TOKEN_STORAGE_KEY } from "../lib/token";
import type { UserOut } from "../api/types";

interface AuthValue {
  token: string | null;
  user: UserOut | null;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [token, setTokenState] = useState<string | null>(getToken());

  const meQuery = useQuery({
    queryKey: ["me", token],
    enabled: !!token,
    queryFn: async ({ signal }) => (await api.get<UserOut>("/auth/me", {
      signal,
      headers: { Authorization: `Bearer ${token}` },
    })).data,
    retry: false,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    function sync() {
      const next = getToken();
      if (next === token) return;
      qc.clear();
      setTokenState(next);
    }
    function onStorage(event: StorageEvent) {
      if (event.storageArea === window.localStorage &&
          (event.key === TOKEN_STORAGE_KEY || event.key === null)) sync();
    }
    window.addEventListener("storage", onStorage);
    sync();
    return () => window.removeEventListener("storage", onStorage);
  }, [qc, token]);

  const login = useCallback((newToken: string) => {
    qc.clear();
    setToken(newToken);
    setTokenState(newToken);
  }, [qc]);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    qc.clear();
  }, [qc]);

  const value = useMemo<AuthValue>(
    () => ({
      token,
      user: meQuery.data ?? null,
      isLoading: !!token && meQuery.isLoading,
      login,
      logout,
    }),
    [token, meQuery.data, meQuery.isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
