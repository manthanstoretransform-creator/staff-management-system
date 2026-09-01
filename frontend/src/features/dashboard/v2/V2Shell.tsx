import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/authContext";
import { brandGradient } from "./theme";

const getInitials = (name: string) => {
  if (!name) return "ST";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
};

/** The four detail reports, mirrored in the sidebar and the report-type switcher. */
export const REPORT_LINKS = [
  { id: "projects", label: "Project-Wise" },
  { id: "tasks", label: "Top Tasks" },
  { id: "apps", label: "App-Wise" },
  { id: "urls", label: "URL-Wise" },
];

/** Brand mark from the Monitra logo: gradient ring + check. */
export const BrandMark: React.FC<{ size?: number }> = ({ size = 40 }) => (
  <div
    className="flex shrink-0 items-center justify-center rounded-xl shadow-md"
    style={{ width: size, height: size, background: brandGradient }}
  >
    <svg width={size * 0.55} height={size * 0.55} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="3">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 6" />
    </svg>
  </div>
);

export const V2Shell: React.FC<{
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  breadcrumb?: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, subtitle, actions, breadcrumb, children }) => {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const onReports = location.pathname.startsWith("/dashboard/reports");
  const onV2 = location.pathname === "/dashboard";
  const onTeams = location.pathname.startsWith("/admin/teams");
  const [reportsOpen, setReportsOpen] = useState(onReports);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  // Color accents for the brand
  const brandGradient = "linear-gradient(135deg, #0ea5e9 0%, #3b82f6 50%, #8b5cf6 100%)";

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F8FAFC] font-sans text-slate-800">
      
      {/* Mobile Sidebar Overlay */}
      <div 
        className={`fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm transition-opacity lg:hidden ${mobileMenuOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setMobileMenuOpen(false)}
      />

      {/* Sidebar - Made premium with deep rich blue/black and modern accents */}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[280px] shrink-0 flex-col justify-between border-r border-slate-800 bg-[#0B1220] p-6 text-slate-400 transition-transform duration-300 lg:static lg:translate-x-0 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex min-h-0 flex-grow flex-col">
          <div className="mb-8 flex shrink-0 items-center gap-3.5">
            <BrandMark size={38} />
            <div>
              <div className="text-base font-bold leading-none tracking-tight text-white">Monitra</div>
              <div className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">Workspace</div>
            </div>
            {/* Close button for mobile */}
            <button 
              className="ml-auto lg:hidden text-slate-400 hover:text-white"
              onClick={() => setMobileMenuOpen(false)}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>

          <div className="min-h-0 flex-grow space-y-1 overflow-y-auto custom-scrollbar">

            {/* Dashboard — sits directly below Task Listing */}
            <button
              onClick={() => { navigate("/dashboard"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (onV2
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={onV2 ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (onV2 ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"
                />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.488 9A9.004 9.004 0 0015 3.512V9h5.488z" />
              </svg>
              <span className="flex-1">Dashboard</span>
            </button>

            {/* Reports — expandable group, one entry per detail report */}
            <div>
              <button
                onClick={() => setReportsOpen((open) => !open)}
                className={
                  "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                  (onReports
                    ? "bg-slate-800/60 text-white"
                    : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
                }
              >
                <svg className="h-5 w-5 text-[#22D3EE]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 17v-6m4 6V7m4 10v-4M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
                <span className="flex-1">Reports</span>
                <svg
                  className={"h-3.5 w-3.5 transition-transform " + (reportsOpen ? "rotate-180" : "")}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {reportsOpen && (
                <ul className="ml-6 mt-1 space-y-0.5 border-l border-slate-800 pl-2.5">
                  {REPORT_LINKS.map((report) => {
                    const active = location.pathname === `/dashboard/reports/${report.id}`;
                    return (
                      <li key={report.id}>
                        <button
                          onClick={() => { navigate(`/dashboard/reports/${report.id}`); setMobileMenuOpen(false); }}
                          className={
                            "flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] font-medium transition duration-150 " +
                            (active
                              ? "bg-[#2563EB]/15 text-white"
                              : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
                          }
                        >
                          <span
                            className={
                              "h-1.5 w-1.5 shrink-0 rounded-full " + (active ? "bg-[#22D3EE]" : "bg-slate-600")
                            }
                          />
                          {report.label}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Project Management */}
            <button
              onClick={() => { navigate("/admin/project-management"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (location.pathname === "/admin/project-management"
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={location.pathname === "/admin/project-management" ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (location.pathname === "/admin/project-management" ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <span className="flex-1">Project management</span>
            </button>

            {/* Task Listing */}
            <button
              onClick={() => { navigate("/admin/task-listing"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (location.pathname === "/admin/task-listing"
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={location.pathname === "/admin/task-listing" ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (location.pathname === "/admin/task-listing" ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <span className="flex-1">Task Listing</span>
            </button>
            <button
              onClick={() => { navigate("/admin/members"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (location.pathname === "/admin/members"
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={location.pathname === "/admin/members" ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (location.pathname === "/admin/members" ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
              <span className="flex-1">Members</span>
            </button>

            {/* Time Tracking */}
            <button
              onClick={() => { navigate("/admin/time-tracking"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (location.pathname === "/admin/time-tracking"
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={location.pathname === "/admin/time-tracking" ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (location.pathname === "/admin/time-tracking" ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="flex-1">Time Tracking</span>
            </button>

            {/* Screenshots */}
            <button
              onClick={() => { navigate("/admin/screenshots"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (location.pathname === "/admin/screenshots"
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={location.pathname === "/admin/screenshots" ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (location.pathname === "/admin/screenshots" ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="flex-1">Screenshots</span>
            </button>

            {/* Teams — leader > projects > members drill-down */}
            <button
              onClick={() => { navigate("/admin/teams"); setMobileMenuOpen(false); }}
              className={
                "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3.5 py-3 text-left text-sm font-medium leading-snug transition duration-150 " +
                (onTeams
                  ? "text-white shadow-sm"
                  : "text-[#94A3B8] hover:bg-slate-800/40 hover:text-white")
              }
              style={onTeams ? { background: brandGradient } : undefined}
            >
              <svg
                className={"h-5 w-5 " + (onTeams ? "text-white" : "text-[#22D3EE]")}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              <span className="flex-1">Teams</span>
            </button>
          </div>
        </div>

        <div className="shrink-0 space-y-4 border-t border-slate-800 pt-4">
          {currentUser && (
            <div className="flex items-center gap-3 rounded-xl border border-slate-700/40 bg-slate-800/60 p-3">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white"
                style={{ background: brandGradient }}
              >
                {getInitials(currentUser.name)}
              </div>
              <div className="min-w-0 flex-grow">
                <div className="truncate text-xs font-semibold leading-normal text-white" title={currentUser.name}>
                  {currentUser.name}
                </div>
                <div className="truncate text-[10px] leading-normal text-[#64748B]" title={currentUser.email}>
                  {currentUser.email}
                </div>
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-slate-800 px-4 py-2.5 text-sm font-semibold text-[#94A3B8] transition hover:bg-slate-700 hover:text-white"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-grow flex-col">
        <header className="flex min-h-16 shrink-0 items-center gap-4 border-b border-[#E2E8F0] bg-white px-4 lg:px-8 py-3">
          <button 
            className="lg:hidden shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            onClick={() => setMobileMenuOpen(true)}
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="min-w-0 flex-1">
            {breadcrumb}
            <h1 className="truncate text-lg font-bold tracking-tight text-[#0F172A]">{title}</h1>
            {subtitle && <p className="mt-0.5 truncate text-xs text-[#64748B]">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>

        <main className="flex-grow overflow-y-auto p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
};
