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
import { MemberDashboard } from './features/member/MemberDashboard'
import { MemberReports } from './features/member/MemberReports'
import { MemberProjects } from './features/member/MemberProjects'
import { MemberTasks } from './features/member/MemberTasks'
import { MemberTimeTracking } from './features/member/MemberTimeTracking'
import { MemberScreenshots } from './features/member/MemberScreenshots'
import { MemberTeam } from './features/member/MemberTeam'
import type { UserRead } from './api/auth'

const ADMIN_ROLES = ["admin", "org_admin", "super_admin"];

/** Roles that may open the organization-management screens under `/admin`. */
const isAdminUser = (user: UserRead | null) => !!user && ADMIN_ROLES.includes(user.role_name);

/**
 * Whether this user's reports and dashboard cover the whole organization.
 *
 * This is the permission the backend actually checks, not a role list. It
 * matters that the two agree: without `time_entries:view_all` the Dashboard
 * and Reports endpoints pin `member_id` to the caller, so a user who lacks it
 * belongs on the member screens, and a manager who has it — an admin role by
 * capability but not by name — still belongs on the org-wide ones.
 */
const canViewAllTime = (user: UserRead | null) => !!user?.permissions?.["time_entries:view_all"];

/**
 * Where a signed-in user belongs.
 *
 * The org-wide screens read the whole organization and the member screens read
 * one person's own work, so "home" is not the same route for everyone. Every
 * redirect in this file goes through here rather than hard-coding
 * `/dashboard`, which used to drop a member onto a page whose every request
 * they are forbidden to make.
 */
const homeFor = (user: UserRead | null) => (canViewAllTime(user) ? "/dashboard" : "/member/dashboard");

const LoadingScreen: React.FC<{ label: string }> = ({ label }) => (
  <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
    <div className="text-sm font-semibold text-[#64748B]">{label}</div>
  </div>
);

/** The `/admin` management screens: roster, project and team administration. */
const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, currentUser, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen label="Loading session..." />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return isAdminUser(currentUser) ? <>{children}</> : <Navigate to={homeFor(currentUser)} replace />;
};

/** The org-wide Dashboard and Reports, which need `time_entries:view_all`. */
const OrgWideRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, currentUser, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen label="Loading session..." />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return canViewAllTime(currentUser) ? <>{children}</> : <Navigate to="/member/dashboard" replace />;
};

/**
 * The member screens.
 *
 * A user who can see everyone's time is sent to the org-wide dashboard rather
 * than shown a member's: these pages are answered by the same endpoints, and
 * for them `member_id` is *not* pinned — so "My Dashboard" would quietly show
 * the whole organization's numbers under a personal heading.
 */
const MemberRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, currentUser, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen label="Loading session..." />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return canViewAllTime(currentUser) ? <Navigate to="/dashboard" replace /> : <>{children}</>;
};

const AppRoutes: React.FC = () => {
  const { isAuthenticated, currentUser, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen label="Loading authentication..." />;

  const home = homeFor(currentUser);

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to={home} replace /> : <LoginScreen />}
      />

      {/* ------------------------------------------------------ admin */}
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
        path="/dashboard"
        element={
          <OrgWideRoute>
            <DashboardV2 />
          </OrgWideRoute>
        }
      />
      <Route
        path="/dashboard/reports/:reportId"
        element={
          <OrgWideRoute>
            <ReportPage />
          </OrgWideRoute>
        }
      />

      {/* ----------------------------------------------------- member */}
      <Route
        path="/member/dashboard"
        element={
          <MemberRoute>
            <MemberDashboard />
          </MemberRoute>
        }
      />
      <Route
        path="/member/reports"
        element={<Navigate to="/member/reports/projects" replace />}
      />
      <Route
        path="/member/reports/:reportId"
        element={
          <MemberRoute>
            <MemberReports />
          </MemberRoute>
        }
      />
      <Route
        path="/member/projects"
        element={
          <MemberRoute>
            <MemberProjects />
          </MemberRoute>
        }
      />
      <Route
        path="/member/tasks"
        element={
          <MemberRoute>
            <MemberTasks />
          </MemberRoute>
        }
      />
      <Route
        path="/member/time-tracking"
        element={
          <MemberRoute>
            <MemberTimeTracking />
          </MemberRoute>
        }
      />
      <Route
        path="/member/screenshots"
        element={
          <MemberRoute>
            <MemberScreenshots />
          </MemberRoute>
        }
      />
      <Route
        path="/member/team"
        element={
          <MemberRoute>
            <MemberTeam />
          </MemberRoute>
        }
      />
      <Route
        path="/member/team/:projectId"
        element={
          <MemberRoute>
            <MemberTeam />
          </MemberRoute>
        }
      />

      <Route path="*" element={<Navigate to={isAuthenticated ? home : "/login"} replace />} />
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
