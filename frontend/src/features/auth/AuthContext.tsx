import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getMe, login as loginRequest, register as registerRequest, type RegisterInput } from "../../api/auth";
import { ApiError, setStoredToken, getStoredToken } from "../../api/client";
import type { User } from "../../types/api";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(() => getStoredToken());

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: Boolean(token),
    retry: false,
  });

  useEffect(() => {
    if (meQuery.error instanceof ApiError && meQuery.error.status === 401 && token) {
      setStoredToken(null);
      setToken(null);
    }
  }, [meQuery.error, token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: meQuery.data ?? null,
      isLoading: Boolean(token) && meQuery.isLoading,
      login: async (email, password) => {
        const result = await loginRequest(email, password);
        setStoredToken(result.access_token);
        setToken(result.access_token);
        queryClient.setQueryData(["me"], result.user);
      },
      register: async (input) => {
        const result = await registerRequest(input);
        setStoredToken(result.access_token);
        setToken(result.access_token);
        queryClient.setQueryData(["me"], result.user);
      },
      logout: () => {
        setStoredToken(null);
        setToken(null);
        queryClient.clear();
      },
    }),
    [meQuery.data, meQuery.isLoading, queryClient, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
