import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './features/auth/authContext'
import { LoginScreen } from './features/auth/LoginScreen'
import { DashboardV2 } from './features/dashboard/v2/DashboardV2'
import { ReportPage } from './features/dashboard/v2/ReportPage'
import { AdminProjectManagement } from './features/admin/AdminProjectManagement'
import { AdminTaskListing } from './features/admin/AdminTaskListing'
import { AdminTeams } from './features/admin/AdminTeams'
import { AdminMembers } from './features/admin/AdminMembers'
import { AdminTimeTracking } from './features/admin/AdminTimeTracking'
import { AdminScreenshots } from './features/admin/AdminScreenshots'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
        <div className="text-sm font-semibold text-[#64748B]">Loading session...</div>
      </div>
    );
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, currentUser, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
        <div className="text-sm font-semibold text-[#64748B]">Loading session...</div>
      </div>
    );
  }

  const isAdmin = currentUser?.role_name === "admin" || currentUser?.role_name === "org_admin" || currentUser?.role_name === "super_admin";

  return isAuthenticated && isAdmin ? <>{children}</> : <Navigate to="/dashboard-v2" replace />;
};

const AppRoutes: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
        <div className="text-sm font-semibold text-[#64748B]">Loading authentication...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard-v2" replace /> : <LoginScreen />}
      />
      <Route
        path="/admin/project-management"
        element={
          <AdminRoute>
            <AdminProjectManagement />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/task-listing"
        element={
          <AdminRoute>
            <AdminTaskListing />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/members"
        element={
          <AdminRoute>
            <AdminMembers />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/time-tracking"
        element={
          <AdminRoute>
            <AdminTimeTracking />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/screenshots"
        element={
          <AdminRoute>
            <AdminScreenshots />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/teams"
        element={
          <AdminRoute>
            <AdminTeams />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/teams/:leaderId"
        element={
          <AdminRoute>
            <AdminTeams />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/teams/:leaderId/:projectId"
        element={
          <AdminRoute>
            <AdminTeams />
          </AdminRoute>
        }
      />
      <Route
        path="/dashboard-v2"
        element={
          <ProtectedRoute>
            <DashboardV2 />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard-v2/reports/:reportId"
        element={
          <ProtectedRoute>
            <ReportPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="*"
        element={<Navigate to={isAuthenticated ? "/dashboard-v2" : "/login"} replace />}
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
