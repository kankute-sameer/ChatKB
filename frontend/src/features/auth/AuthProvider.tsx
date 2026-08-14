import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, clearToken, getToken, setToken } from "@/lib/api";

interface AuthContextValue {
  username: string | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    let cancelled = false;
    api<{ username: string }>("/auth/me")
      .then((user) => {
        if (!cancelled) setUsername(user.username);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearToken();
        }
        if (!cancelled) setUsername(null);
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      username,
      ready,
      login: async (name: string, password: string) => {
        const token = await api<{ access_token: string }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ username: name, password }),
        });
        setToken(token.access_token);
        const me = await api<{ username: string }>("/auth/me");
        setUsername(me.username);
      },
      logout: () => {
        clearToken();
        setUsername(null);
      },
    }),
    [username, ready],
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
