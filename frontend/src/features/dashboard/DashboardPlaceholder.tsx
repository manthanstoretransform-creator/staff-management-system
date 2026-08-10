import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/authContext";

export const DashboardPlaceholder: React.FC = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-sans">
      {/* Sidebar - dark theme */}
      <aside className="w-[290px] bg-[#0B1220] text-white flex flex-col justify-between p-6">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#2563EB] to-purple-600 flex items-center justify-center font-bold text-white shadow-md text-lg">
              S
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              StaffTrack
            </span>
          </div>
          <nav className="space-y-2">
            <div className="px-4 py-2.5 bg-[#2563EB] rounded-lg text-white font-medium flex items-center gap-2 cursor-pointer">
              Dashboard
            </div>
          </nav>
        </div>
        <div>
          <button
            onClick={handleLogout}
            className="w-full px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-[#94A3B8] hover:text-white rounded-lg transition text-sm font-semibold flex items-center justify-center gap-2"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-grow p-8 flex flex-col justify-center items-center">
        <div className="max-w-md w-full bg-white p-8 rounded-xl border border-[#E2E8F0] shadow-sm text-center">
          <div className="w-16 h-16 bg-blue-50 text-[#2563EB] rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-[#0F172A] mb-2">
            Dashboard — coming soon
          </h1>
          <p className="text-sm text-[#64748B] mb-6">
            The tracking dashboard and reporting analytics will be available in the next phase.
          </p>
        </div>
      </main>
    </div>
  );
};
