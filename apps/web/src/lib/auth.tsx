import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { get, post } from "./api";
import type { Me, Role } from "./types";

interface AuthState {
  user: Me | null;
  loading: boolean;
  setUser: (user: Me | null) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<Me>("/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const signOut = useCallback(async () => {
    await post("/auth/logout").catch(() => undefined);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, setUser, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function hasRole(user: Me | null, ...roles: Role[]): boolean {
  return !!user && roles.some((r) => user.roles.includes(r));
}

export function homePath(user: Me): string {
  return user.is_platform_admin ? "/admin/companies" : "/app";
}
