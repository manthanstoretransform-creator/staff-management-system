import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/authContext";

interface Project {
  id: number;
  project_name: string;
  description?: string;
  status: string;
  is_billable: boolean;
  start_date?: string;
}

interface ProjectMember {
  id: number;
  project_id: number;
  user_id: number;
  joined_at: string;
}

interface Employee {
  id: number;
  name: string;
  email: string;
  role_name: string;
  is_active: boolean;
}

export const AdminProjects: React.FC = () => {
  const { accessToken, currentUser, logout } = useAuth();
  const navigate = useNavigate();

  // Projects State
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Employees List (for membership selection)
  const [employees, setEmployees] = useState<Employee[]>([]);

  // Selected Project Members state
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [isMembersLoading, setIsMembersLoading] = useState(false);
  const [newMemberUserId, setNewMemberUserId] = useState<string>("");

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);

  // Form Fields
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const [isBillable, setIsBillable] = useState(true);
  const [startDate, setStartDate] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // Fetch projects and employees
  const fetchInitialData = async () => {
    if (!accessToken) return;
    try {
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

      // Only show active/planning non-archived projects
      setProjects(projData.filter((p: Project) => p.status !== "archived"));
      setEmployees(empData);
    } catch (err: any) {
      setError(err.message || "An error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchInitialData();
  }, [accessToken]);

  // Fetch project members when selected project changes
  useEffect(() => {
    const fetchMembers = async () => {
      if (!selectedProject || !accessToken) return;
      setIsMembersLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/projects/${selectedProject.id}/members`, {
          headers: { "Authorization": `Bearer ${accessToken}` }
        });
        if (!response.ok) throw new Error("Failed to fetch project members.");
        const data = await response.json();
        setMembers(data);
      } catch (err: any) {
        console.error(err.message);
      } finally {
        setIsMembersLoading(false);
      }
    };
    fetchMembers();
  }, [selectedProject, accessToken]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim() || !accessToken) return;
    setIsSubmitting(true);
    setFormError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/projects`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          project_name: projectName.trim(),
          description: description.trim() || undefined,
          is_billable: isBillable,
          start_date: startDate || undefined
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to create project.");
      }

      setIsCreateOpen(false);
      fetchInitialData();
    } catch (err: any) {
      setFormError(err.message || "An error occurred.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !projectName.trim() || !accessToken) return;
    setIsSubmitting(true);
    setFormError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/projects/${selectedProject.id}`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          project_name: projectName.trim(),
          description: description.trim() || undefined,
          is_billable: isBillable,
          start_date: startDate || undefined
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to update project.");
      }

      setIsEditOpen(false);
      fetchInitialData();
      setSelectedProject(null);
    } catch (err: any) {
      setFormError(err.message || "An error occurred.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArchiveProject = async (id: number) => {
    if (!accessToken) return;
    if (!window.confirm("Are you sure you want to archive/delete this project?")) return;

    try {
      const response = await fetch(`${API_BASE_URL}/projects/${id}/archive`, {
        method: "PATCH",
        headers: { "Authorization": `Bearer ${accessToken}` }
      });
      if (!response.ok) throw new Error("Failed to archive project.");
      fetchInitialData();
      if (selectedProject?.id === id) {
        setSelectedProject(null);
      }
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !newMemberUserId || !accessToken) return;

    try {
      const response = await fetch(`${API_BASE_URL}/projects/${selectedProject.id}/members`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ user_id: parseInt(newMemberUserId) })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to add member.");
      }

      setNewMemberUserId("");
      // Trigger refetch of project members
      const updatedRes = await fetch(`${API_BASE_URL}/projects/${selectedProject.id}/members`, {
        headers: { "Authorization": `Bearer ${accessToken}` }
      });
      const data = await updatedRes.json();
      setMembers(data);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRemoveMember = async (userId: number) => {
    if (!selectedProject || !accessToken) return;
    if (!window.confirm("Are you sure you want to remove this member from the project?")) return;

    try {
      const response = await fetch(`${API_BASE_URL}/projects/${selectedProject.id}/members/${userId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${accessToken}` }
      });

      if (!response.ok) throw new Error("Failed to remove project member.");

      // Trigger refetch of project members
      const updatedRes = await fetch(`${API_BASE_URL}/projects/${selectedProject.id}/members`, {
        headers: { "Authorization": `Bearer ${accessToken}` }
      });
      const data = await updatedRes.json();
      setMembers(data);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const openCreateModal = () => {
    setProjectName("");
    setDescription("");
    setIsBillable(true);
    setStartDate("");
    setFormError(null);
    setIsCreateOpen(true);
  };

  const openEditModal = (proj: Project) => {
    setSelectedProject(proj);
    setProjectName(proj.project_name);
    setDescription(proj.description || "");
    setIsBillable(proj.is_billable);
    setStartDate(proj.start_date || "");
    setFormError(null);
    setIsEditOpen(true);
  };

  // Map employee name/email details
  const getEmployeeDetails = (userId: number) => {
    const emp = employees.find((e) => e.id === userId);
    return emp ? { name: emp.name, email: emp.email } : { name: `User #${userId}`, email: "Unknown" };
  };

  // Filter employees eligible to be added (not already members)
  const eligibleEmployees = employees.filter(
    (emp) => emp.is_active && !members.some((m) => m.user_id === emp.id)
  );

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#F8FAFC]">
      {/* Left Sidebar */}
      <aside className="w-64 bg-[#0B1220] text-slate-400 p-6 flex flex-col justify-between shrink-0 font-sans border-r border-slate-800">
        <div className="flex flex-col flex-grow min-h-0">
          {/* Brand Logo */}
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
              className="w-full text-left px-3.5 py-3 rounded-lg bg-[#2563EB] text-white shadow-sm transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Manage Projects</span>
            </button>

            <button
              onClick={() => navigate("/admin/tasks")}
              className="w-full text-left px-3.5 py-3 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
            >
              <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <span>Task Listing</span>
            </button>
          </div>
        </div>

        {/* Profile and Sign Out */}
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

      {/* Projects Dashboard Area */}
      <div className="flex-grow flex flex-col min-w-0">
        <header className="h-16 border-b border-[#E2E8F0] bg-white px-8 flex items-center justify-between shrink-0">
          <h1 className="text-lg font-semibold text-[#0F172A]">Workspace Projects Management</h1>
          <button
            onClick={openCreateModal}
            className="bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition shadow-sm cursor-pointer"
          >
            Create Project
          </button>
        </header>

        {/* Content Layout: Projects table + Project membership sidebar */}
        <div className="flex-grow flex min-h-0 bg-[#F8FAFC]">
          {/* Main List */}
          <main className="flex-grow p-8 overflow-y-auto min-h-0">
            {isLoading ? (
              <div className="h-64 flex flex-col items-center justify-center gap-3">
                <svg className="animate-spin h-8 w-8 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span className="text-sm text-[#64748B]">Loading projects...</span>
              </div>
            ) : error ? (
              <div className="bg-white p-6 rounded-xl border border-red-100 shadow-sm text-center">
                <span className="text-sm text-red-500 font-medium">{error}</span>
              </div>
            ) : (
              <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-sm">
                <table className="min-w-full divide-y divide-[#E2E8F0]">
                  <thead className="bg-[#F8FAFC]">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Project Name</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Status</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-[#64748B] uppercase tracking-wider">Type</th>
                      <th className="px-6 py-4 text-right text-xs font-semibold text-[#64748B] uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0] bg-white">
                    {projects.map((proj) => {
                      const isSelected = selectedProject?.id === proj.id;
                      return (
                        <tr
                          key={proj.id}
                          className={`hover:bg-[#F8FAFC]/50 transition cursor-pointer ${
                            isSelected ? "bg-blue-50/40" : ""
                          }`}
                          onClick={() => setSelectedProject(proj)}
                        >
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-semibold text-[#0F172A]">{proj.project_name}</div>
                            {proj.description && (
                              <div className="text-xs text-[#64748B] truncate max-w-md mt-0.5">{proj.description}</div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                              proj.status === "active"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : "bg-slate-50 text-slate-600 border-slate-200"
                            }`}>
                              {proj.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-[#0F172A]">
                            {proj.is_billable ? "Billable" : "Internal / Non-Billable"}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-3" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => openEditModal(proj)}
                              className="text-[#2563EB] hover:text-blue-700 font-semibold cursor-pointer"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleArchiveProject(proj.id)}
                              className="text-red-500 hover:text-red-700 font-semibold cursor-pointer"
                            >
                              Archive
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </main>

          {/* Members Sidebar */}
          <aside className="w-80 border-l border-[#E2E8F0] bg-white p-6 flex flex-col shrink-0 min-h-0">
            {selectedProject ? (
              <div className="flex flex-col h-full min-h-0">
                <div className="border-b border-[#E2E8F0] pb-4 shrink-0">
                  <h3 className="text-sm font-bold text-[#0F172A] truncate" title={selectedProject.project_name}>
                    {selectedProject.project_name}
                  </h3>
                  <p className="text-xs text-[#64748B] mt-1 uppercase tracking-wider font-semibold">Assign Project Members</p>
                </div>

                {/* Add Member Form */}
                <form onSubmit={handleAddMember} className="py-4 border-b border-[#E2E8F0] shrink-0 space-y-3">
                  <label htmlFor="employee-select" className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">
                    Select Employee to Assign
                  </label>
                  <div className="space-y-3">
                    <select
                      id="employee-select"
                      value={newMemberUserId}
                      onChange={(e) => setNewMemberUserId(e.target.value)}
                      className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white font-medium focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none transition"
                      required
                    >
                      <option value="">-- Choose Employee --</option>
                      {eligibleEmployees.map((emp) => (
                        <option key={emp.id} value={emp.id}>
                          {emp.name} ({emp.email})
                        </option>
                      ))}
                    </select>
                    <button
                      type="submit"
                      className="w-full bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs px-4 py-2.5 rounded-lg cursor-pointer transition shadow-sm"
                    >
                      Assign Member
                    </button>
                  </div>
                </form>

                {/* Member List */}
                <div className="flex-grow overflow-y-auto pt-4 min-h-0 space-y-3 pr-1">
                  <div className="text-xs font-semibold text-[#64748B] mb-2">Assigned Workspace Members:</div>
                  {isMembersLoading ? (
                    <div className="text-center text-xs text-[#64748B] py-4">Loading members...</div>
                  ) : members.length === 0 ? (
                    <div className="text-center text-xs text-[#64748B] py-4 italic">No members assigned to this project yet.</div>
                  ) : (
                    members.map((m) => {
                      const details = getEmployeeDetails(m.user_id);
                      return (
                        <div key={m.id} className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-[#0F172A] truncate">{details.name}</div>
                            <div className="text-[10px] text-[#64748B] truncate mt-0.5">{details.email}</div>
                          </div>
                          <button
                            onClick={() => handleRemoveMember(m.user_id)}
                            className="text-red-500 hover:text-red-700 text-xs font-semibold cursor-pointer shrink-0"
                          >
                            Remove
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-center text-xs text-[#64748B] italic">
                Select a project from the table to manage its assigned employees
              </div>
            )}
          </aside>
        </div>
      </div>

      {/* Create Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-xl max-w-md w-full p-6 space-y-6">
            <div>
              <h3 className="text-lg font-bold text-[#0F172A]">Create New Project</h3>
              <p className="text-xs text-[#64748B] mt-1">Set up a new workspace project</p>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-500 font-semibold">
                  {formError}
                </div>
              )}

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">Project Name *</label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white"
                  placeholder="e.g. Project Delta"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white h-20 resize-none"
                  placeholder="Brief project summary..."
                />
              </div>

              <div className="flex items-center justify-between p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">
                <div className="min-w-0">
                  <div className="text-xs font-bold text-[#0F172A]">Billable Project</div>
                  <div className="text-[10px] text-[#64748B] mt-0.5">Toggle if client billing is enabled</div>
                </div>
                <input
                  type="checkbox"
                  checked={isBillable}
                  onChange={(e) => setIsBillable(e.target.checked)}
                  className="w-4 h-4 text-[#2563EB] rounded cursor-pointer"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-[#64748B] hover:text-[#0F172A] border border-[#E2E8F0] rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs px-4 py-2 rounded-lg cursor-pointer transition shadow-sm"
                >
                  {isSubmitting ? "Creating..." : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {isEditOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-xl max-w-md w-full p-6 space-y-6">
            <div>
              <h3 className="text-lg font-bold text-[#0F172A]">Edit Project</h3>
              <p className="text-xs text-[#64748B] mt-1">Update project configuration settings</p>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-100 rounded-lg text-xs text-red-500 font-semibold">
                  {formError}
                </div>
              )}

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">Project Name *</label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white h-20 resize-none"
                />
              </div>

              <div className="flex items-center justify-between p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">
                <div className="min-w-0">
                  <div className="text-xs font-bold text-[#0F172A]">Billable Project</div>
                  <div className="text-[10px] text-[#64748B] mt-0.5">Toggle if client billing is enabled</div>
                </div>
                <input
                  type="checkbox"
                  checked={isBillable}
                  onChange={(e) => setIsBillable(e.target.checked)}
                  className="w-4 h-4 text-[#2563EB] rounded cursor-pointer"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-bold text-[#64748B] uppercase tracking-wider">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full text-sm rounded-lg border border-[#E2E8F0] px-3.5 py-2.5 bg-white"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsEditOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-[#64748B] hover:text-[#0F172A] border border-[#E2E8F0] rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs px-4 py-2 rounded-lg cursor-pointer transition shadow-sm"
                >
                  {isSubmitting ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
