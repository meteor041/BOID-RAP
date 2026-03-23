import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

type AuthUser = {
  id: string;
  username: string;
  role: "admin" | "user";
  enabled: boolean;
};

type LoginPayload = {
  token: string;
  expires_at: string;
  user: AuthUser;
};

type AuthContextValue = {
  token: string | null;
  expiresAt: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => void;
  logout: () => void;
};

const STORAGE_KEY = "boid-rap-auth";

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as {
        token: string | null;
        expiresAt: string | null;
        user: AuthUser | null;
      };
      setToken(parsed.token);
      setExpiresAt(parsed.expiresAt);
      setUser(parsed.user);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      expiresAt,
      user,
      isAuthenticated: Boolean(token && user),
      login: (payload) => {
        setToken(payload.token);
        setExpiresAt(payload.expires_at);
        setUser(payload.user);
        window.localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            token: payload.token,
            expiresAt: payload.expires_at,
            user: payload.user,
          }),
        );
      },
      logout: () => {
        setToken(null);
        setExpiresAt(null);
        setUser(null);
        window.localStorage.removeItem(STORAGE_KEY);
      },
    }),
    [expiresAt, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
