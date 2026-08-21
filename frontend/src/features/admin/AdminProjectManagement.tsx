import React, { useState, useMemo } from 'react';
import { V2Shell } from '../dashboard/v2/V2Shell';
// Leaders, employees and the project seed live in one shared module so the
// Teams page and this page never drift apart.
import {
  EMPLOYEES,
  INITIAL_PROJECTS,
  LEADERS,
  STATUSES,
  type BillingMode,
  type Project,
  type ProjectStatus,
  type Task,
} from './teamData';

// Premium colors based on Monitra branding
const GRADIENT_BLUE_PURPLE = 'bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6]';
const GRADIENT_TEAL_BLUE = 'bg-gradient-to-r from-[#14B8A6] to-[#3B82F6]';
// Based on the user's uploaded image (Cyan to Purple)
const GRADIENT_CYAN_PURPLE = 'bg-gradient-to-r from-[#0ea5e9] via-[#3b82f6] to-[#8b5cf6]';

const StatusBadge: React.FC<{ status: ProjectStatus }> = ({ status }) => {
  switch (status) {
    case 'Active':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#3B82F6] border border-[#3B82F6]">Active</span>;
    case 'Pending':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#F59E0B] border border-[#F59E0B]">Pending</span>;
    case 'To Do':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#64748B] border border-[#CBD5E1]">To Do</span>;
    case 'Completed':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#10B981] border border-[#10B981]">Completed</span>;
    default:
      return null;
  }
};

/**
 * Billing at a glance: an hour budget when the project is billed by fixed
 * hours, "No Limit" when it is billed but open ended, and a muted marker when
 * it is not billed at all.
 */
const BillingBadge: React.FC<{ project: Project }> = ({ project }) => {
  if (!project.billable) {
    return <span className="inline-flex items-center rounded-md bg-slate-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-slate-500 border border-slate-200">Not Billable</span>;
  }
  if (project.billingMode === 'Free Time') {
    return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#14B8A6] border border-[#14B8A6]">No Limit</span>;
  }
  return (
    <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#8B5CF6] border border-[#8B5CF6]">
      {project.billingHours ?? 0} Hours
    </span>
  );
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const day = String(date.getDate()).padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short' });
  const year = date.getFullYear();
  return `${day} ${month} ${year}`; // e.g., 12 Jun 2026
};

export const AdminProjectManagement: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>(INITIAL_PROJECTS);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<ProjectStatus | 'All'>('All');
  
  // Date filter state
  const [dateFilterOpen, setDateFilterOpen] = useState(false);
  const [datePreset, setDatePreset] = useState<string>('All Time');
  const [filterStartDate, setFilterStartDate] = useState('');
  const [filterEndDate, setFilterEndDate] = useState('');
  
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  // Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create');
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formLeader, setFormLeader] = useState('');
  const [formDeadline, setFormDeadline] = useState('');
  const [formStatus, setFormStatus] = useState<ProjectStatus>('Active');
  const [formEmployees, setFormEmployees] = useState<string[]>([]);
  const [formTasks, setFormTasks] = useState<Task[]>([]);
  // Billing: `formBillable` drives the Yes/No radio; the mode + hours are only
  // read back when billing is on.
  const [formBillable, setFormBillable] = useState(false);
  const [formBillingMode, setFormBillingMode] = useState<BillingMode>('Fixed Hours');
  const [formBillingHours, setFormBillingHours] = useState('');
  const [isEmpDropdownOpen, setIsEmpDropdownOpen] = useState(false);
  const [employeeSearch, setEmployeeSearch] = useState('');

  // Modals and Dropdowns
  const [viewEmployeesProj, setViewEmployeesProj] = useState<Project | null>(null);
  const [viewProjectDetails, setViewProjectDetails] = useState<Project | null>(null);
  const [statusMenuOpenForId, setStatusMenuOpenForId] = useState<string | null>(null);

  const openCreateDrawer = () => {
    setDrawerMode('create');
    setEditingId(null);
    setFormName('');
    setFormDescription('');
    setFormLeader('');
    setFormDeadline('');
    setFormStatus('Active');
    setFormEmployees([]);
    setFormTasks([]);
    setFormBillable(false);
    setFormBillingMode('Fixed Hours');
    setFormBillingHours('');
    setEmployeeSearch('');
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (proj: Project) => {
    setDrawerMode('edit');
    setEditingId(proj.id);
    setFormName(proj.name);
    setFormDescription(proj.description || '');
    setFormLeader(proj.leaderId);
    setFormDeadline(proj.deadline);
    setFormStatus(proj.status);
    setFormEmployees(proj.employees);
    setFormTasks(proj.tasks || []);
    setFormBillable(proj.billable ?? false);
    setFormBillingMode(proj.billingMode || 'Fixed Hours');
    setFormBillingHours(proj.billingHours ? String(proj.billingHours) : '');
    setEmployeeSearch('');
    setIsDrawerOpen(true);
  };

  const handleLeaderChange = (leaderId: string) => {
    setFormLeader(leaderId);
    // User requested: "show all employee not leader wise", so we DO NOT clear employees when leader changes.
    // However, tasks might still apply, so we leave them intact too.
  };

  const handleSaveProject = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName || !formLeader || !formDeadline) return;
    // A fixed-hours project is meaningless without an hour budget.
    if (formBillable && formBillingMode === 'Fixed Hours' && !formBillingHours) return;

    const billingFields = {
      billable: formBillable,
      billingMode: formBillable ? formBillingMode : undefined,
      billingHours:
        formBillable && formBillingMode === 'Fixed Hours' ? Number(formBillingHours) : undefined,
    };

    if (drawerMode === 'create') {
      const newProj: Project = {
        id: `p${Date.now()}`,
        name: formName,
        description: formDescription,
        leaderId: formLeader,
        deadline: formDeadline,
        status: formStatus,
        employees: formEmployees,
        tasks: formTasks,
        ...billingFields,
      };
      setProjects([newProj, ...projects]);
    } else if (drawerMode === 'edit' && editingId) {
      setProjects(projects.map(p => p.id === editingId ? {
        ...p,
        name: formName,
        description: formDescription,
        leaderId: formLeader,
        deadline: formDeadline,
        status: formStatus,
        employees: formEmployees,
        tasks: formTasks,
        ...billingFields,
      } : p));
    }
    setIsDrawerOpen(false);
  };

  const applyDatePreset = (preset: string) => {
    const today = new Date();
    let start = new Date(today);
    let end = new Date(today);

    switch (preset) {
      case 'Today':
        break;
      case 'Tomorrow':
        start.setDate(today.getDate() + 1);
        end = new Date(start);
        break;
      case 'Next 7 days':
        end.setDate(today.getDate() + 6);
        break;
      case 'Next week':
        start.setDate(today.getDate() + 7);
        end.setDate(today.getDate() + 13);
        break;
      case 'Next 2 weeks':
        end.setDate(today.getDate() + 13);
        break;
      case 'This month':
        start = new Date(today.getFullYear(), today.getMonth(), 1);
        end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        break;
      case 'Next month':
        start = new Date(today.getFullYear(), today.getMonth() + 1, 1);
        end = new Date(today.getFullYear(), today.getMonth() + 2, 0);
        break;
    }
    
    const format = (d: Date) => {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${y}-${m}-${day}`;
    };

    return { start: format(start), end: format(end) };
  };

  const filteredProjects = useMemo(() => {
    return projects.filter(p => {
      const matchSearch = p.name.toLowerCase().includes(search.toLowerCase());
      const matchStatus = filterStatus === 'All' || p.status === filterStatus;
      let matchDate = true;
      if (filterStartDate || filterEndDate) {
        if (filterStartDate && p.deadline < filterStartDate) matchDate = false;
        if (filterEndDate && p.deadline > filterEndDate) matchDate = false;
      }
      return matchSearch && matchStatus && matchDate;
    });
  }, [projects, search, filterStatus, filterStartDate, filterEndDate]);

  const totalPages = Math.ceil(filteredProjects.length / PAGE_SIZE);
  const paginatedProjects = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredProjects.slice(start, start + PAGE_SIZE);
  }, [filteredProjects, page]);

  // ALL employees are available now, regardless of the selected leader.
  const availableEmployees = EMPLOYEES;

  return (
    <V2Shell
      title="V2 Project Management"
      subtitle="Manage projects, leaders, and assign employees."
      actions={
        <div className="flex gap-2">
          <button
            onClick={openCreateDrawer}
            className={`rounded-lg px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
          >
            + Create Project
          </button>
        </div>
      }
    >
      <div className="mx-auto max-w-7xl space-y-6 pb-20">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-1 items-center gap-2 px-2">
            <svg className="h-5 w-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search projects by name..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 text-slate-700"
            />
          </div>
          
          <div className="h-8 w-px bg-slate-200 hidden lg:block"></div>

          <div className="flex flex-wrap items-center gap-4">
            {/* Status Filter */}
            <div className="flex items-center gap-3 border-r border-slate-200 pr-4">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATUS:</span>
              <select
                value={filterStatus}
                onChange={(e) => { setFilterStatus(e.target.value as any); setPage(1); }}
                className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none focus:border-[#38bdf8] hover:bg-slate-50 shadow-sm"
              >
                <option value="All">All Statuses</option>
                {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            {/* Deadline Filter */}
            <div className="relative">
              <button
                onClick={() => setDateFilterOpen(!dateFilterOpen)}
                className="flex items-center gap-2 rounded-lg border border-[#38bdf8] bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 shadow-sm"
              >
                <span className="text-[#0ea5e9]">
                  {datePreset !== 'All Time' ? datePreset : (filterStartDate ? `${filterStartDate} to ${filterEndDate || 'Any'}` : 'Filter Deadline')}
                </span>
                <svg className="h-4 w-4 text-[#0ea5e9]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>
              
              {dateFilterOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setDateFilterOpen(false)} />
                  <div className="absolute right-0 z-20 mt-2 flex w-[480px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl animate-in fade-in slide-in-from-top-2">
                    {/* Left Side: Presets */}
                    <div className="w-1/3 border-r border-slate-100 bg-slate-50 p-2 space-y-1">
                      {['All Time', 'Today', 'Tomorrow', 'Next 7 days', 'Next week', 'Next 2 weeks', 'This month', 'Next month'].map(preset => (
                        <button
                          key={preset}
                          onClick={() => {
                            setDatePreset(preset);
                            if (preset === 'All Time') {
                              setFilterStartDate('');
                              setFilterEndDate('');
                            } else {
                              const { start, end } = applyDatePreset(preset);
                              setFilterStartDate(start);
                              setFilterEndDate(end);
                            }
                            setPage(1);
                          }}
                          className={`w-full rounded-md px-3 py-2 text-left text-xs font-semibold transition ${datePreset === preset ? 'bg-white border border-slate-200 text-[#0ea5e9] shadow-sm' : 'text-slate-600 hover:bg-slate-200/50'}`}
                        >
                          {preset}
                        </button>
                      ))}
                    </div>
                    {/* Right Side: Simple Custom Inputs to act like calendar selection */}
                    <div className="w-2/3 p-4">
                        <h4 className="mb-4 text-sm font-bold text-slate-800">Custom Range</h4>
                        <div className="space-y-4">
                          <div>
                            <label className="mb-1 block text-xs font-semibold text-slate-500">Start Date</label>
                            <input 
                              type="date"
                              value={filterStartDate}
                              onChange={(e) => {
                                setFilterStartDate(e.target.value);
                                setDatePreset('Custom');
                                setPage(1);
                              }}
                              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8]"
                            />
                          </div>
                          <div>
                            <label className="mb-1 block text-xs font-semibold text-slate-500">End Date</label>
                            <input 
                              type="date"
                              value={filterEndDate}
                              onChange={(e) => {
                                setFilterEndDate(e.target.value);
                                setDatePreset('Custom');
                                setPage(1);
                              }}
                              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8]"
                            />
                          </div>
                        </div>
                        
                        <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
                          <button 
                            onClick={() => {
                              setFilterStartDate('');
                              setFilterEndDate('');
                              setDatePreset('All Time');
                              setPage(1);
                            }}
                            className="rounded-md px-3 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-100"
                          >
                            Clear
                          </button>
                          <button 
                            onClick={() => setDateFilterOpen(false)}
                            className="rounded-md bg-[#0ea5e9] px-4 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-sky-500 transition"
                          >
                            Apply
                          </button>
                        </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto pb-4">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Project Name</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Description</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Leader Name</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Employee</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Deadline</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Billing</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px] text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paginatedProjects.map(proj => {
                  const leader = LEADERS.find(l => l.id === proj.leaderId);
                  return (
                    <tr key={proj.id} className="transition hover:bg-slate-50/50">
                      <td className="px-6 py-4 font-semibold text-slate-800">{proj.name}</td>
                      <td className="px-6 py-4">
                        <div 
                          className="max-w-[150px] truncate text-slate-500 text-xs cursor-help"
                          title={proj.description || 'No description'}
                        >
                          {proj.description || <span className="italic text-slate-400">No description</span>}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-600 font-medium">{leader?.name || 'Unassigned'}</td>
                      <td className="px-6 py-4">
                        <button 
                          onClick={() => setViewEmployeesProj(proj)}
                          className="inline-flex items-center justify-center rounded-md bg-[#3B82F6]/10 px-2.5 py-1.5 text-xs font-bold text-[#2563EB] transition hover:bg-[#3B82F6]/20"
                        >
                          View Employees ({proj.employees.length})
                        </button>
                      </td>
                      <td className="px-6 py-4 relative">
                        <button 
                          onClick={() => setStatusMenuOpenForId(statusMenuOpenForId === proj.id ? null : proj.id)} 
                          className="focus:outline-none flex items-center gap-1 group"
                        >
                          <StatusBadge status={proj.status} />
                        </button>
                        
                        {/* Dropdown Popover */}
                        {statusMenuOpenForId === proj.id && (
                          <>
                            <div className="fixed inset-0 z-[90]" onClick={() => setStatusMenuOpenForId(null)} />
                            <div className="absolute top-12 left-6 z-[100] mt-1 w-44 rounded-xl bg-white shadow-[0_10px_25px_-5px_rgba(0,0,0,0.1),_0_8px_10px_-6px_rgba(0,0,0,0.1)] border border-slate-100 p-3 animate-in fade-in zoom-in-95 duration-150">
                              <div className="flex flex-col gap-2.5">
                                {STATUSES.map(s => (
                                  <button 
                                    key={s} 
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setProjects(projects.map(p => p.id === proj.id ? { ...p, status: s } : p));
                                      setStatusMenuOpenForId(null);
                                    }}
                                    className={`text-left w-full rounded-md px-2 py-1.5 transition ${proj.status === s ? 'bg-slate-50' : 'hover:bg-slate-50'}`}
                                  >
                                    <StatusBadge status={s} />
                                  </button>
                                ))}
                              </div>
                            </div>
                          </>
                        )}
                      </td>
                      <td className="px-6 py-4 text-slate-600">{formatDate(proj.deadline)}</td>
                      <td className="px-6 py-4"><BillingBadge project={proj} /></td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setViewProjectDetails(proj)}
                            className="rounded px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 border border-slate-200 transition hover:bg-slate-100 hover:text-slate-800"
                          >
                            View
                          </button>
                          <button
                            onClick={() => openEditDrawer(proj)}
                            className="rounded px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-wider text-[#14B8A6] border border-[#14B8A6]/30 transition hover:bg-[#14B8A6]/10"
                          >
                            Edit
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {paginatedProjects.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-slate-500">
                      No projects found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 bg-white px-6 py-3">
              <span className="text-xs text-slate-500">
                Showing {((page - 1) * PAGE_SIZE) + 1} to {Math.min(page * PAGE_SIZE, filteredProjects.length)} of {filteredProjects.length} Entries
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition disabled:opacity-40 hover:bg-slate-50"
                >
                  Prev
                </button>
                <span className="px-3 text-xs font-bold text-slate-800">{page} / {totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition disabled:opacity-40 hover:bg-slate-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Slide-over Drawer for Create / Edit */}
      <div className={`fixed inset-0 z-50 overflow-hidden ${isDrawerOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        <div 
          className={`absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-300 ${isDrawerOpen ? 'opacity-100' : 'opacity-0'}`} 
          onClick={() => setIsDrawerOpen(false)} 
        />
        <div className={`absolute inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isDrawerOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
              <h3 className="text-lg font-bold text-slate-800">
                {drawerMode === 'create' ? 'Create New Project' : 'Edit Project'}
              </h3>
              <button type="button" onClick={() => setIsDrawerOpen(false)} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <form id="project-form" onSubmit={handleSaveProject} className="p-6 space-y-6">
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Project Name</label>
                  <input
                    required
                    type="text"
                    value={formName}
                    onChange={e => setFormName(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    placeholder="Enter project name..."
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Description</label>
                  <textarea
                    value={formDescription}
                    onChange={e => setFormDescription(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium min-h-[80px]"
                    placeholder="Enter project description..."
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Status</label>
                  <select
                    required
                    value={formStatus}
                    onChange={e => setFormStatus(e.target.value as ProjectStatus)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium bg-white"
                  >
                    {STATUSES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Assign Leader</label>
                  <select
                    required
                    value={formLeader}
                    onChange={e => handleLeaderChange(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium bg-white"
                  >
                    <option value="">Select a leader...</option>
                    {LEADERS.map(l => (
                      <option key={l.id} value={l.id}>{l.name}</option>
                    ))}
                  </select>
                </div>

                {/* Employees Section - Dropdown multi-select */}
                <div className="relative">
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Select Employees</label>
                  
                  <button
                    type="button"
                    onClick={() => setIsEmpDropdownOpen(!isEmpDropdownOpen)}
                    className="w-full flex items-center justify-between rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                  >
                    <span>
                      {formEmployees.length > 0 
                        ? `${formEmployees.length} employee${formEmployees.length > 1 ? 's' : ''} selected` 
                        : 'Select employees...'}
                    </span>
                    <svg className={`w-4 h-4 text-slate-400 transition-transform ${isEmpDropdownOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  
                  {isEmpDropdownOpen && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setIsEmpDropdownOpen(false)}></div>
                      <div className="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-xl animate-in fade-in slide-in-from-top-2 overflow-hidden flex flex-col">
                        <div className="p-2 border-b border-slate-100 bg-slate-50">
                          <input 
                            type="text" 
                            placeholder="Search employee..." 
                            value={employeeSearch}
                            onChange={e => setEmployeeSearch(e.target.value)}
                            className="w-full text-xs px-3 py-1.5 rounded border border-slate-200 outline-none focus:border-[#3B82F6]"
                          />
                        </div>
                        <div className="max-h-60 overflow-y-auto p-2">
                          {availableEmployees.filter(emp => emp.name.toLowerCase().includes(employeeSearch.toLowerCase())).map(emp => (
                            <label key={emp.id} className="flex cursor-pointer items-center gap-3 rounded p-2 hover:bg-slate-50">
                              <input 
                                type="checkbox" 
                                checked={formEmployees.includes(emp.id)}
                                onChange={(e) => {
                                  if (e.target.checked) setFormEmployees([...formEmployees, emp.id]);
                                  else {
                                    setFormEmployees(formEmployees.filter(id => id !== emp.id));
                                    setFormTasks(formTasks.filter(t => t.assigneeId !== emp.id));
                                  }
                                }}
                                className="h-4 w-4 rounded border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                              />
                              <span className="text-sm font-medium text-slate-700">{emp.name}</span>
                            </label>
                          ))}
                          {availableEmployees.filter(emp => emp.name.toLowerCase().includes(employeeSearch.toLowerCase())).length === 0 && (
                            <div className="text-xs text-slate-400 text-center py-4">No employees found.</div>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                  <p className="mt-1.5 text-[11px] text-slate-500">Select multiple employees for this project.</p>
                </div>

                {/* Tasks Section - Always Visible */}
                <div className="border-t border-slate-100 pt-6">
                  <div className="flex items-center justify-between mb-4">
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">Project Tasks</label>
                    <button 
                      type="button"
                      disabled={formEmployees.length === 0}
                      onClick={() => setFormTasks([...formTasks, { id: `t${Date.now()}`, name: '', assigneeId: '', status: 'To Do' }])}
                      className="text-xs font-bold text-[#3B82F6] hover:text-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      + Add Task
                    </button>
                  </div>
                  
                  {formEmployees.length === 0 ? (
                    <div className="p-4 text-center rounded-lg border border-slate-200 border-dashed bg-slate-50 text-xs text-slate-400">
                      Please select employees first to assign tasks.
                    </div>
                  ) : (
                    <div className="space-y-4 animate-in fade-in duration-300">
                      {formTasks.map((task, index) => (
                        <div key={task.id} className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-3 relative group">
                          <button 
                            type="button"
                            onClick={() => setFormTasks(formTasks.filter((_, i) => i !== index))}
                            className="absolute -top-2 -right-2 bg-white border border-slate-200 rounded-full p-1 text-slate-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition shadow-sm"
                          >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                          </button>
                          
                          <div>
                            <input 
                              type="text" 
                              placeholder="Task Name"
                              value={task.name}
                              onChange={e => {
                                const newTasks = [...formTasks];
                                newTasks[index].name = e.target.value;
                                setFormTasks(newTasks);
                              }}
                              className="w-full text-sm rounded border border-slate-300 px-3 py-1.5 outline-none focus:border-[#3B82F6]"
                              required
                            />
                          </div>
                          <div className="flex gap-2">
                            <select 
                              value={task.assigneeId}
                              onChange={e => {
                                const newTasks = [...formTasks];
                                newTasks[index].assigneeId = e.target.value;
                                setFormTasks(newTasks);
                              }}
                              className="w-1/2 text-xs rounded border border-slate-300 px-2 py-1.5 outline-none focus:border-[#3B82F6] bg-white"
                              required
                            >
                              <option value="">Assignee...</option>
                              {formEmployees.map(empId => {
                                const emp = EMPLOYEES.find(e => e.id === empId);
                                return <option key={empId} value={empId}>{emp?.name}</option>;
                              })}
                            </select>
                            
                            <select 
                              value={task.status}
                              onChange={e => {
                                const newTasks = [...formTasks];
                                newTasks[index].status = e.target.value as any;
                                setFormTasks(newTasks);
                              }}
                              className="w-1/2 text-xs rounded border border-slate-300 px-2 py-1.5 outline-none focus:border-[#3B82F6] bg-white"
                            >
                              <option value="To Do">To Do</option>
                              <option value="In Progress">In Progress</option>
                              <option value="Completed">Completed</option>
                            </select>
                          </div>
                        </div>
                      ))}
                      {formTasks.length === 0 && (
                        <div className="text-center py-4 text-xs text-slate-400 italic bg-slate-50 border border-slate-200 border-dashed rounded-lg">
                          No tasks added yet. Click "+ Add Task" to create one.
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Deadline</label>
                  <input
                    required
                    type="date"
                    value={formDeadline}
                    onChange={e => setFormDeadline(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                  />
                </div>

                {/* Billing - Yes reveals the two timing modes */}
                <div className="border-t border-slate-100 pt-6">
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Billing</label>
                  <div className="flex gap-3">
                    {[{ label: 'Yes', value: true }, { label: 'No', value: false }].map(opt => (
                      <label
                        key={opt.label}
                        className={`flex flex-1 cursor-pointer items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition ${
                          formBillable === opt.value
                            ? 'border-[#3B82F6] bg-blue-50/60 text-[#3B82F6]'
                            : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                        }`}
                      >
                        <input
                          type="radio"
                          name="billing"
                          checked={formBillable === opt.value}
                          onChange={() => setFormBillable(opt.value)}
                          className="h-4 w-4 border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                        />
                        {opt.label}
                      </label>
                    ))}
                  </div>

                  {formBillable && (
                    <div className="mt-4 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 animate-in fade-in duration-300">
                      <label
                        className={`flex cursor-pointer items-start gap-3 rounded-lg border bg-white px-3 py-2.5 transition ${
                          formBillingMode === 'Fixed Hours' ? 'border-[#3B82F6]' : 'border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="billingMode"
                          checked={formBillingMode === 'Fixed Hours'}
                          onChange={() => setFormBillingMode('Fixed Hours')}
                          className="mt-0.5 h-4 w-4 border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                        />
                        <span>
                          <span className="block text-sm font-medium text-slate-700">Fixed Hours</span>
                          <span className="block text-[11px] text-slate-500">Timeline of the project in hours.</span>
                        </span>
                      </label>

                      {formBillingMode === 'Fixed Hours' && (
                        <div className="pl-7">
                          <div className="relative">
                            <input
                              required
                              type="number"
                              min={1}
                              step={1}
                              placeholder="Enter total hours..."
                              value={formBillingHours}
                              onChange={e => setFormBillingHours(e.target.value)}
                              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 pr-16 text-sm font-medium outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                            />
                            <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-xs font-medium text-slate-400">hours</span>
                          </div>
                        </div>
                      )}

                      <label
                        className={`flex cursor-pointer items-start gap-3 rounded-lg border bg-white px-3 py-2.5 transition ${
                          formBillingMode === 'Free Time' ? 'border-[#3B82F6]' : 'border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="billingMode"
                          checked={formBillingMode === 'Free Time'}
                          onChange={() => setFormBillingMode('Free Time')}
                          className="mt-0.5 h-4 w-4 border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                        />
                        <span>
                          <span className="block text-sm font-medium text-slate-700">Free Time</span>
                          <span className="block text-[11px] text-slate-500">No time limit on this project.</span>
                        </span>
                      </label>
                    </div>
                  )}
                </div>
              </form>
            </div>
            
            <div className="border-t border-slate-100 p-6 bg-slate-50">
              <button
                type="submit"
                form="project-form"
                className={`w-full rounded-lg px-6 py-3 text-sm font-bold text-white shadow-md hover:opacity-90 transition-opacity ${GRADIENT_CYAN_PURPLE}`}
              >
                {drawerMode === 'create' ? 'Create Project' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* View Employees Modal (from Table click) */}
      {viewEmployeesProj && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-white shadow-xl border border-slate-100 animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
              <h3 className="text-[15px] font-bold text-slate-800">
                Employees in <span className="text-[#3B82F6]">{viewEmployeesProj.name}</span>
              </h3>
              <button type="button" onClick={() => setViewEmployeesProj(null)} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 max-h-[60vh] overflow-y-auto">
              {viewEmployeesProj.employees.length > 0 ? (
                <ul className="space-y-3">
                  {viewEmployeesProj.employees.map(empId => {
                    const emp = EMPLOYEES.find(e => e.id === empId);
                    const empTasks = viewEmployeesProj.tasks?.filter(t => t.assigneeId === empId) || [];
                    
                    return (
                      <li key={empId} className="flex flex-col gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3 shadow-sm">
                        <div className="flex items-center gap-3">
                          <div className={`flex h-8 w-8 items-center justify-center rounded-full text-[10px] font-bold text-white ${GRADIENT_BLUE_PURPLE}`}>
                            {emp?.name.substring(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-sm font-bold text-slate-800">{emp?.name || 'Unknown'}</div>
                            <div className="text-[11px] text-slate-500">Employee</div>
                          </div>
                        </div>
                        {empTasks.length > 0 && (
                          <div className="mt-1 pl-11 space-y-2">
                            {empTasks.map(t => (
                              <div key={t.id} className="text-xs flex items-center justify-between bg-white border border-slate-200 p-2 rounded">
                                <span className="font-medium text-slate-700">{t.name}</span>
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                  t.status === 'Completed' ? 'bg-emerald-100 text-emerald-700' :
                                  t.status === 'In Progress' ? 'bg-blue-100 text-blue-700' :
                                  'bg-slate-100 text-slate-600'
                                }`}>
                                  {t.status}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="py-6 text-center text-sm font-medium text-slate-400">
                  No employees assigned to this project.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* View Project Details Modal (from Action column) */}
      {viewProjectDetails && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl border border-slate-100 animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
              <h3 className="text-[15px] font-bold text-slate-800">Project Details</h3>
              <button type="button" onClick={() => setViewProjectDetails(null)} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="rounded-xl border border-slate-100 bg-slate-50 p-5 space-y-4">
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Project Name</div>
                  <div className="mt-1 text-lg font-bold text-slate-800">{viewProjectDetails.name}</div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Status</div>
                    <div className="mt-1">
                      <StatusBadge status={viewProjectDetails.status} />
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Employees</div>
                    <div className="mt-1 text-sm font-bold text-[#14B8A6]">
                      {viewProjectDetails.employees.length} Members Assigned
                    </div>
                  </div>
                </div>
                {viewProjectDetails.description && (
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Description</div>
                    <div className="mt-1 text-sm text-slate-600 bg-white p-3 rounded border border-slate-100">{viewProjectDetails.description}</div>
                  </div>
                )}
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Leader</div>
                  <div className="mt-1 text-sm font-medium text-slate-700">
                    {LEADERS.find(l => l.id === viewProjectDetails.leaderId)?.name || 'Unassigned'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Deadline</div>
                  <div className="mt-1 text-sm font-medium text-slate-700">{formatDate(viewProjectDetails.deadline)}</div>
                </div>
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Billing</div>
                  <div className="mt-1 text-sm font-medium text-slate-700">
                    {!viewProjectDetails.billable
                      ? 'No'
                      : viewProjectDetails.billingMode === 'Fixed Hours'
                        ? `Yes - Fixed Hours (${viewProjectDetails.billingHours ?? 0} hours)`
                        : 'Yes - Free Time (no limit)'}
                  </div>
                </div>
              </div>
            </div>
            <div className="border-t border-slate-100 p-4 bg-slate-50 flex justify-end">
              <button
                onClick={() => setViewProjectDetails(null)}
                className="rounded-lg bg-white border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </V2Shell>
  );
};
