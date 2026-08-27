import React, { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { loginAPI, getMeAPI } from "../../api/auth";
import { store } from "../../store";
import { baseApi } from "../../store/api/baseApi";
import { clearPersistedApiCache } from "../../store/persist";
import type { UserRead } from "../../api/auth";

interface AuthContextType {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  currentUser: UserRead | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const PROFILE_KEY = "monitra.session.user.v1";

/**
 * The profile from the last verified session.
 *
 * Keeping it lets the app render its real screens on the first frame after a
 * refresh instead of holding everything behind a round trip to /auth/me. It is
 * a rendering convenience only - it grants nothing. Every request still carries
 * the token and the backend still authorises it, and the check below revokes
 * the session the moment the server disagrees.
 */
const readCachedProfile = (): UserRead | null => {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw) as { token?: string; user?: UserRead };
    // Bound to the token it was fetched with, so a different session never
    // renders as the previous user even for a frame.
    if (!cached?.user || cached.token !== localStorage.getItem("accessToken")) return null;
    return cached.user;
  } catch {
    return null;
  }
};

const writeCachedProfile = (user: UserRead | null) => {
  try {
    if (user) {
      localStorage.setItem(PROFILE_KEY, JSON.stringify({ token: localStorage.getItem("accessToken"), user }));
    } else {
      localStorage.removeItem(PROFILE_KEY);
    }
  } catch {
    /* storage unavailable - the app just starts cold next time */
  }
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Seed straight from storage so the first render already knows who is signed
  // in. `getMeAPI` below still runs and still has the last word.
  const restored = localStorage.getItem("accessToken") && localStorage.getItem("refreshToken")
    ? readCachedProfile()
    : null;

  const [accessToken, setAccessToken] = useState<string | null>(restored ? localStorage.getItem("accessToken") : null);
  const [refreshToken, setRefreshToken] = useState<string | null>(restored ? localStorage.getItem("refreshToken") : null);
  const [currentUser, setCurrentUser] = useState<UserRead | null>(restored);
  const [isLoading, setIsLoading] = useState<boolean>(!restored);

  // Restore authentication from localStorage on application mount
  useEffect(() => {
    const restoreAuth = async () => {
      const storedAccess = localStorage.getItem("accessToken");
      const storedRefresh = localStorage.getItem("refreshToken");

      if (storedAccess && storedRefresh) {
        try {
          // Verify the token and pick up any profile change. When we already
          // restored from cache this runs behind the rendered UI; otherwise the
          // app waits on it exactly as before.
          const user = await getMeAPI(storedAccess);
          setAccessToken(storedAccess);
          setRefreshToken(storedRefresh);
          setCurrentUser(user);
          writeCachedProfile(user);
        } catch (err) {
          console.error("Failed to restore session, clearing invalid tokens:", err);
          localStorage.removeItem("accessToken");
          localStorage.removeItem("refreshToken");
          writeCachedProfile(null);
          clearPersistedApiCache();
          store.dispatch(baseApi.util.resetApiState());
          setAccessToken(null);
          setRefreshToken(null);
          setCurrentUser(null);
        }
      } else {
        writeCachedProfile(null);
      }
      setIsLoading(false);
    };

    restoreAuth();
  }, []);

  const login = async (email: string, password: string) => {
    try {
      const response = await loginAPI({ email, password });
      
      // Save tokens in browser storage to survive browser refreshes
      localStorage.setItem("accessToken", response.access_token);
      localStorage.setItem("refreshToken", response.refresh_token);
      // A previous account's cache must never leak into this session.
      store.dispatch(baseApi.util.resetApiState());
      clearPersistedApiCache();
      
      setAccessToken(response.access_token);
      setRefreshToken(response.refresh_token);
      setCurrentUser(response.user);
      writeCachedProfile(response.user);
    } catch (err) {
      throw err;
    }
  };

  const logout = () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    // Cached responses belong to the account that fetched them - drop both the
    // in-memory cache and the copy on disk so the next sign-in starts clean.
    store.dispatch(baseApi.util.resetApiState());
    clearPersistedApiCache();
    writeCachedProfile(null);
    setAccessToken(null);
    setRefreshToken(null);
    setCurrentUser(null);
  };

  const isAuthenticated = !!accessToken && !!currentUser;

  return (
    <AuthContext.Provider
      value={{
        accessToken,
        refreshToken,
        isAuthenticated,
        currentUser,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
