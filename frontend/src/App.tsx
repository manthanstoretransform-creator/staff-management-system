import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './features/auth/authContext'
import { LoginScreen } from './features/auth/LoginScreen'
import { ProjectList } from './features/projects/ProjectList'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppRoutes: React.FC = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginScreen />}
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <ProjectList />
          </ProtectedRoute>
        }
      />
      <Route
        path="*"
        element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />}
      />
    </Routes>
  );
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
