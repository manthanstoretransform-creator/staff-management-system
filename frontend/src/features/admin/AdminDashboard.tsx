import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/authContext";

interface DashboardStats {
  total_projects: number;
  total_members: number;
  total_tasks: number;
  total_hours_tracked: number;
}

export const AdminDashboard: React.FC = () => {
  const { accessToken, currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getInitials = (name: string) => {
    if (!name) return "ST";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  useEffect(() => {
    const fetchStats = async () => {
      if (!accessToken) {
        navigate("/login");
        return;
      }
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
        const response = await fetch(`${API_BASE_URL}/employees/dashboard-stats`, {
          headers: {
            "Authorization": `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
        });
        if (!response.ok) {
          throw new Error("Failed to load dashboard metrics.");
        }
        const data = await response.json();
        setStats(data);
      } catch (err: any) {
        setError(err.message || "An error occurred.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchStats();
  }, [accessToken, navigate]);

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#F8FAFC]">
      {/* Left Sidebar */}
      <aside className="w-64 bg-[#0B1220] text-slate-400 p-6 flex flex-col justify-between shrink-0 font-sans border-r border-slate-800">
        <div className="flex flex-col flex-grow min-h-0">
          {/* Brand/Logo Header */}
          <div className="flex items-center gap-3.5 mb-8 shrink-0">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-[#2563EB] to-purple-600 flex items-center justify-center font-extrabold text-white shadow-sm text-lg">
              S
            </div>
            <div>
              <div className="font-bold text-white text-base tracking-tight leading-none">
                StaffTrack
              </div>
              <div className="text-[10px] text-[#64748B] font-semibold tracking-wider uppercase mt-1">
                Workspace
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="flex-grow overflow-y-auto min-h-0 space-y-1">
            <button
              onClick={() => navigate("/dashboard")}
              className="w-full text-left px-3.5 py-3 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span>Projects Dashboard</span>
            </button>

            <button
              className="w-full text-left px-3.5 py-3 rounded-lg bg-[#2563EB] text-white shadow-sm transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Admin Dashboard</span>
            </button>
          </div>
        </div>

        {/* Profile Card & Sign Out */}
        <div className="pt-4 border-t border-slate-800 shrink-0 space-y-4">
          {currentUser && (
            <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-700/40 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-[#2563EB] to-purple-600 flex items-center justify-center font-bold text-white text-sm shrink-0">
                {getInitials(currentUser.name)}
              </div>
              <div className="min-w-0 flex-grow">
                <div className="font-semibold text-white text-xs truncate leading-normal" title={currentUser.name}>
                  {currentUser.name}
                </div>
                <div className="text-[10px] text-[#64748B] truncate leading-normal" title={currentUser.email}>
                  {currentUser.email}
                </div>
                <div className="text-[10px] text-[#2563EB] font-bold mt-0.5 uppercase tracking-wider leading-none">
                  {currentUser.role_name === "employee" ? "Employee" : currentUser.role_name === "admin" || currentUser.role_name === "org_admin" ? "Admin" : currentUser.role_name}
                </div>
              </div>
            </div>
          )}

          <button
            onClick={handleLogout}
            className="w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-[#94A3B8] hover:text-white rounded-lg transition text-sm font-semibold flex items-center justify-center gap-2"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Stats Area */}
      <div className="flex-grow flex flex-col min-w-0">
        <header className="h-16 border-b border-[#E2E8F0] bg-white px-8 flex items-center">
          <h1 className="text-lg font-semibold text-[#0F172A]">Admin Workspace Analytics</h1>
        </header>

        <main className="flex-grow p-8 overflow-y-auto space-y-8">
          {isLoading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-3">
              <svg className="animate-spin h-8 w-8 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-sm text-[#64748B]">Loading admin workspace stats...</span>
            </div>
          ) : error ? (
            <div className="max-w-md mx-auto bg-white p-6 rounded-xl border border-red-100 shadow-sm text-center">
              <span className="text-sm text-red-500 font-medium">{error}</span>
            </div>
          ) : stats ? (
            <div className="space-y-8">
              {/* Metrics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {/* Card 1: Projects */}
                <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Total Projects</div>
                    <div className="text-2xl font-bold text-[#0F172A] mt-1">{stats.total_projects}</div>
                  </div>
                </div>

                {/* Card 2: Members */}
                <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-purple-50 flex items-center justify-center text-purple-600 shrink-0">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Active Members</div>
                    <div className="text-2xl font-bold text-[#0F172A] mt-1">{stats.total_members}</div>
                  </div>
                </div>

                {/* Card 3: Tasks */}
                <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 shrink-0">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Active Tasks</div>
                    <div className="text-2xl font-bold text-[#0F172A] mt-1">{stats.total_tasks}</div>
                  </div>
                </div>

                {/* Card 4: Hours */}
                <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 shrink-0">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Hours Tracked</div>
                    <div className="text-2xl font-bold text-[#0F172A] mt-1">{stats.total_hours_tracked}h</div>
                  </div>
                </div>
              </div>

              {/* Productivity & Filter Section Area */}
              <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-4">
                  <h3 className="text-base font-bold text-[#0F172A]">Workspace Productivity Report</h3>
                  <div className="text-xs text-[#64748B] font-semibold bg-[#F1F5F9] px-3 py-1.5 rounded-lg">
                    Current Period (Total)
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                  <div className="space-y-2">
                    <div className="text-sm font-semibold text-[#64748B]">Overview Summary</div>
                    <p className="text-sm text-[#0F172A] leading-relaxed">
                      Across all active projects in your organization, a total of <strong>{stats.total_hours_tracked} hours</strong> have been logged. This encompasses both automatic stopwatch timer tracking and approved manual logs.
                    </p>
                  </div>
                  <div className="bg-[#F8FAFC] p-4 rounded-xl border border-[#E2E8F0] flex flex-col justify-center">
                    <div className="text-xs font-bold text-[#64748B] uppercase tracking-wider">Avg. Time per Member</div>
                    <div className="text-3xl font-extrabold text-[#2563EB] mt-2">
                      {stats.total_members > 0 ? (stats.total_hours_tracked / stats.total_members).toFixed(1) : 0}h
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
};
