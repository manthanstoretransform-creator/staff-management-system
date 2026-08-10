import React, { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import { loginAPI } from "../../api/auth";

interface AuthContextType {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);

  const login = async (email: string, password: string) => {
    const tokens = await loginAPI({ email, password });
    setAccessToken(tokens.access_token);
    setRefreshToken(tokens.refresh_token);
  };

  const logout = () => {
    setAccessToken(null);
    setRefreshToken(null);
  };

  const isAuthenticated = !!accessToken;

  return (
    <AuthContext.Provider value={{ accessToken, refreshToken, isAuthenticated, login, logout }}>
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
