import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/authContext";

interface Project {
  id: number;
  project_name: string;
}

interface TaskAssignee {
  user_id: number;
}

interface Task {
  id: number;
  project_id: number;
  task_name: string;
  description?: string;
  status: string;
  due_date?: string;
  time_tracked_seconds: number;
  assignees?: TaskAssignee[];
}

interface Employee {
  id: number;
  name: string;
  email: string;
}

export const AdminTasks: React.FC = () => {
  const { accessToken, currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

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

  const formatTrackedTime = (seconds: number): string => {
    const hours = seconds / 3600.0;
    return `${hours.toFixed(1)}h`;
  };

  const getProjectName = (projectId: number): string => {
    const p = projects.find((proj) => proj.id === projectId);
    return p ? p.project_name : `Project #${projectId}`;
  };

  const getAssigneeNames = (assigneesList?: TaskAssignee[]): string => {
    if (!assigneesList || assigneesList.length === 0) return "Unassigned";
    return assigneesList
      .map((a) => {
        const emp = employees.find((e) => e.id === a.user_id);
        if (emp) return emp.name;
        if (currentUser && currentUser.id === a.user_id) return currentUser.name;
        return `User #${a.user_id}`;
      })
      .join(", ");
  };

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    const fetchAllData = async () => {
      if (!accessToken) {
        navigate("/login");
        return;
      }
      try {
        // 1. Fetch active projects and organization employees
        const [projRes, empRes] = await Promise.all([
          fetch(`${API_BASE_URL}/projects`, {
            headers: { "Authorization": `Bearer ${accessToken}` }
          }),
          fetch(`${API_BASE_URL}/employees?limit=100`, {
            headers: { "Authorization": `Bearer ${accessToken}` }
          })
        ]);

        if (!projRes.ok || !empRes.ok) {
          throw new Error("Failed to load workspace projects or employees list.");
        }

        const projData = await projRes.json();
        const empData = await empRes.json();

        const activeProjects = projData.filter((p: any) => p.status !== "archived");
        setProjects(activeProjects);
        setEmployees(empData);

        // 2. Fetch tasks for each active project in parallel
        const taskRequests = activeProjects.map(async (project: Project) => {
          const res = await fetch(`${API_BASE_URL}/projects/${project.id}/tasks`, {
            headers: { "Authorization": `Bearer ${accessToken}` }
          });
          if (res.ok) {
            return res.json();
          }
          return [];
        });

        const taskResults = await Promise.all(taskRequests);
        const allTasks = taskResults.flat();
        setTasks(allTasks);
      } catch (err: any) {
        setError(err.message || "An error occurred.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchAllData();
  }, [accessToken, navigate]);

  // Filter tasks based on dropdown filter selection
  const filteredTasks = selectedProjectId
    ? tasks.filter((t) => t.project_id === parseInt(selectedProjectId))
    : tasks;

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#F8FAFC]">
      {/* Left Sidebar */}
      <aside className="w-64 bg-[#0B1220] text-slate-400 p-6 flex flex-col justify-between shrink-0 font-sans border-r border-slate-800">
        <div className="flex flex-col flex-grow min-h-0">
          {/* Logo Section */}
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
              onClick={() => navigate("/admin")}
              className="w-full text-left px-3.5 py-3 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span>Admin Dashboard</span>
            </button>

            <button
              onClick={() => navigate("/admin/projects")}
              className="w-full text-left px-3.5 py-3 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Manage Projects</span>
            </button>

            <button
              className="w-full text-left px-3.5 py-3 rounded-lg bg-[#2563EB] text-white shadow-sm transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <span>Task Listing</span>
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

      {/* Main Task List Area */}
      <div className="flex-grow flex flex-col min-w-0">
        <header className="h-16 border-b border-[#E2E8F0] bg-white px-8 flex items-center justify-between shrink-0">
          <h1 className="text-lg font-semibold text-[#0F172A]">Workspace Task Listing</h1>
          
          {/* Dropdown Project Filter */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Project Filter:</span>
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="text-xs rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white font-semibold focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none transition cursor-pointer"
            >
              <option value="">All Projects</option>
              {projects.map((proj) => (
                <option key={proj.id} value={proj.id}>
                  {proj.project_name}
                </option>
              ))}
            </select>
          </div>
        </header>

        <main className="flex-grow p-8 overflow-y-auto min-h-0 bg-[#F8FAFC]">
          {isLoading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-3">
              <svg className="animate-spin h-8 w-8 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-sm text-[#64748B]">Loading workspace tasks...</span>
            </div>
          ) : error ? (
            <div className="bg-white p-6 rounded-xl border border-red-100 shadow-sm text-center">
              <span className="text-sm text-red-500 font-medium">{error}</span>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="bg-white p-12 rounded-2xl border border-[#E2E8F0] shadow-sm text-center">
              <div className="text-sm font-semibold text-[#64748B] italic">No active tasks found matching the filter criteria.</div>
            </div>
          ) : (
            <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-sm">
              <table className="min-w-full divide-y divide-[#E2E8F0]">
                <thead className="bg-[#F8FAFC]">
                  <tr>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Task Name</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Project</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Status</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Assigned Members</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Due Date</th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-[#64748B] uppercase tracking-wider">Tracked Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] bg-white">
                  {filteredTasks.map((task) => (
                    <tr key={task.id} className="hover:bg-[#F8FAFC]/50 transition">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-semibold text-[#0F172A]">{task.task_name}</div>
                        {task.description && (
                          <div className="text-xs text-[#64748B] max-w-sm truncate mt-0.5">{task.description}</div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-[#0F172A] font-medium">
                        {getProjectName(task.project_id)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                          task.status === "completed"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : task.status === "in_progress"
                            ? "bg-blue-50 text-blue-700 border-blue-200"
                            : "bg-slate-50 text-slate-600 border-slate-200"
                        }`}>
                          {task.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-[#64748B]">
                        {getAssigneeNames(task.assignees)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-[#0F172A]">
                        {task.due_date ? task.due_date : "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-bold text-[#0F172A]">
                        {formatTrackedTime(task.time_tracked_seconds)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
