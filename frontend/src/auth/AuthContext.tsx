import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { clearToken, getToken, setToken } from "../lib/token";
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
    queryFn: async () => (await api.get<UserOut>("/auth/me")).data,
    retry: false,
    staleTime: 5 * 60_000,
  });

  const login = useCallback((newToken: string) => {
    setToken(newToken);
    setTokenState(newToken);
  }, []);

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
