import React, { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { loginAPI, getMeAPI } from "../../api/auth";
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

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore authentication from localStorage on application mount
  useEffect(() => {
    const restoreAuth = async () => {
      const storedAccess = localStorage.getItem("accessToken");
      const storedRefresh = localStorage.getItem("refreshToken");

      if (storedAccess && storedRefresh) {
        try {
          // Fetch current user details from backend to verify token validity
          const user = await getMeAPI(storedAccess);
          setAccessToken(storedAccess);
          setRefreshToken(storedRefresh);
          setCurrentUser(user);
        } catch (err) {
          console.error("Failed to restore session, clearing invalid tokens:", err);
          localStorage.removeItem("accessToken");
          localStorage.removeItem("refreshToken");
          setAccessToken(null);
          setRefreshToken(null);
          setCurrentUser(null);
        }
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
      
      setAccessToken(response.access_token);
      setRefreshToken(response.refresh_token);
      setCurrentUser(response.user);
    } catch (err) {
      throw err;
    }
  };

  const logout = () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
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
