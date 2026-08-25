import React, { useState } from 'react';
import { V2Shell } from '../dashboard/v2/V2Shell';
import { 
  useGetProjectMetadataQuery, 
  useGetProjectsQuery, 
  useGetAssignableLeadersQuery, 
  useGetAssignableEmployeesQuery, 
  useCreateProjectMutation, 
  useUpdateProjectMutation, 
  useDeleteProjectMutation,
  useCreateTaskMutation,
  type Project
} from '../../store/api/projectsApi';

const GRADIENT_CYAN_PURPLE = 'bg-gradient-to-r from-[#0ea5e9] via-[#3b82f6] to-[#8b5cf6]';

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return 'No Deadline';
  const parts = dateStr.split('T')[0].split('-');
  if (parts.length !== 3) return dateStr;
  const date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const day = date.getDate().toString().padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short' });
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
};

export const AdminProjectManagement: React.FC = () => {
  const [search, setSearch] = useState('');
  const [filterStatusId, setFilterStatusId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  // RTK Query Hooks
  const { data: metadata } = useGetProjectMetadataQuery();
  const { data: assignableLeaders } = useGetAssignableLeadersQuery();
  const { data: assignableEmployees } = useGetAssignableEmployeesQuery();
  const { data: projectsData, isLoading } = useGetProjectsQuery({ 
    page, 
    limit: PAGE_SIZE, 
    search, 
    status_id: filterStatusId 
  });
  
  const [createProject] = useCreateProjectMutation();
  const [updateProject] = useUpdateProjectMutation();
  const [deleteProject] = useDeleteProjectMutation();
  const [createTask] = useCreateTaskMutation();

  // Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create');
  const [editingId, setEditingId] = useState<number | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formLeader, setFormLeader] = useState<number | string>('');
  const [formDeadline, setFormDeadline] = useState('');
  const [formStatusId, setFormStatusId] = useState<number>(1);
  const [formEmployees, setFormEmployees] = useState<number[]>([]);
  const [formBillingType, setFormBillingType] = useState<'fixed' | 'free'>('fixed');
  const [formBillingHours, setFormBillingHours] = useState('');

  // Dropdown states
  const [isEmpDropdownOpen, setIsEmpDropdownOpen] = useState(false);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormLeader('');
    setFormDeadline('');
    setFormStatusId(metadata?.project_statuses?.[0]?.id || 1);
    setFormEmployees([]);
    setFormBillingType('fixed');
    setFormBillingHours('');
    setIsEmpDropdownOpen(false);
  };

  const openCreateDrawer = () => {
    resetForm();
    setDrawerMode('create');
    setEditingId(null);
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (proj: Project) => {
    setFormName(proj.project_name);
    setFormDescription(proj.description || '');
    setFormLeader(proj.leader?.id || '');
    setFormDeadline(proj.deadline ? proj.deadline.split('T')[0] : '');
    setFormStatusId(proj.status?.id || 1);
    setFormEmployees(proj.employees.filter(e => e.role === 'employee' || e.role === 'Employee').map(e => e.id));
    setFormBillingType(proj.billing_type as 'fixed' | 'free' || 'fixed');
    setFormBillingHours(proj.fixed_hours ? String(proj.fixed_hours) : '');
    
    setDrawerMode('edit');
    setEditingId(proj.id);
    setIsDrawerOpen(true);
  };

  const closeDrawer = () => {
    setIsDrawerOpen(false);
    resetForm();
  };

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName) return;

    const payload = {
      project_name: formName,
      description: formDescription,
      status_id: formStatusId,
      leader_id: formLeader === '' ? null : Number(formLeader),
      employee_ids: formEmployees,
      deadline: formDeadline || null,
      billing_type: formBillingType,
      fixed_hours: formBillingType === 'fixed' && formBillingHours ? Number(formBillingHours) : null,
    };

    try {
      if (drawerMode === 'create') {
        const newProj = await createProject(payload).unwrap();
        
        // Generate 4 default tasks per employee via API
        const defaultTasks = ['Setup Project', 'internal discussion', 'review client update', 'sharing client update'];
        const taskPromises = [];
        
        for (const empId of formEmployees) {
          for (const taskName of defaultTasks) {
            taskPromises.push(
              createTask({
                projectId: newProj.id,
                body: { 
                  name: taskName, 
                  assignee_id: empId, 
                  status_id: metadata?.task_statuses?.[0]?.id || 1 
                }
              }).unwrap().catch(e => console.error('Failed to create default task:', e))
            );
          }
        }
        
        await Promise.all(taskPromises);
      } else if (drawerMode === 'edit' && editingId) {
        await updateProject({ id: editingId, body: payload }).unwrap();
      }
      closeDrawer();
    } catch (err) {
      console.error("Failed to save project:", err);
      alert("Error saving project. Check console.");
    }
  };


  const handleUpdateProjectInline = async (proj: Project, newStatusId?: number, newEmployeeIds?: number[]) => {
    try {
      const payload = {
        project_name: proj.project_name,
        description: proj.description,
        status_id: newStatusId !== undefined ? newStatusId : proj.status?.id,
        leader_id: proj.leader?.id || null,
        employee_ids: newEmployeeIds !== undefined 
          ? newEmployeeIds 
          : proj.employees.filter((e: any) => e.role === 'employee' || e.role === 'Employee').map((e: any) => e.id),
        deadline: proj.deadline ? proj.deadline.split('T')[0] : null,
        billing_type: proj.billing_type || 'fixed',
        fixed_hours: proj.fixed_hours ? Number(proj.fixed_hours) : null,
      };
      await updateProject({ id: proj.id, body: payload }).unwrap();
    } catch (err) {
      console.error(err);
    }
  };

  // State to track which project's team dropdown is open
  const [openTeamDropdownId, setOpenTeamDropdownId] = useState<number | null>(null);

  const handleDelete = async (id: number) => {
    if (confirm("Are you sure you want to delete this project?")) {
      try {
        await deleteProject(id).unwrap();
      } catch (err) {
        console.error("Failed to delete project:", err);
      }
    }
  };

  const projects = projectsData?.items || [];
  const totalPages = projectsData?.pagination?.total_pages || 1;

  return (
    <V2Shell
      title="Project Management"
      subtitle="Manage projects, deadlines, team assignments, and client billing."
      actions={
        <button
          onClick={openCreateDrawer}
          className={`rounded-lg px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
        >
          + Create Project
        </button>
      }
    >
      <div className="mx-auto max-w-[1600px] space-y-8 pb-20">
        
        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="relative w-full sm:max-w-md">
            <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search projects..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6] focus:bg-white focus:ring-1 focus:ring-[#3B82F6]"
            />
          </div>

          <div className="flex w-full sm:w-auto items-center gap-3">
            <select
              value={filterStatusId || ''}
              onChange={e => setFilterStatusId(e.target.value ? Number(e.target.value) : null)}
              className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] sm:w-auto"
            >
              <option value="">All Statuses</option>
              {metadata?.project_statuses?.map(status => (
                <option key={status.id} value={status.id}>{status.project_status}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Project Cards Grid */}
        {isLoading ? (
          <div className="flex justify-center p-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
          </div>
        ) : (
                    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Project</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Leader</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Team</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Tasks</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Billing</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Deadline</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px] text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {projects.map(proj => (
                  <tr key={proj.id} className="group transition hover:bg-slate-50/80">
                    <td className="px-6 py-4">
                      <div className="font-bold text-slate-800">{proj.project_name}</div>
                      <div className="text-xs text-slate-500 truncate max-w-[200px]">{proj.description || '-'}</div>
                    </td>
                    <td className="px-6 py-4 overflow-visible">
                      <select
                        value={proj.status?.id}
                        onChange={(e) => handleUpdateProjectInline(proj, Number(e.target.value), undefined)}
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold shadow-sm outline-none transition focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                        style={{ color: proj.status?.color, borderColor: proj.status?.color }}
                      >
                        {metadata?.project_statuses?.map(s => (
                          <option key={s.id} value={s.id} style={{ color: '#334155' }}>{s.project_status}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm ${GRADIENT_CYAN_PURPLE}`}>
                          {(proj.leader?.name || 'U').substring(0, 2).toUpperCase()}
                        </div>
                        <div className="font-semibold text-slate-700">{proj.leader?.name || 'Unassigned'}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600 relative overflow-visible">
                      <button
                        onClick={() => setOpenTeamDropdownId(openTeamDropdownId === proj.id ? null : proj.id)}
                        className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold shadow-sm outline-none transition hover:bg-slate-50 focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                      >
                        {proj.employee_count} members
                        <svg className="h-3 w-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
                      </button>
                      
                      {openTeamDropdownId === proj.id && (
                        <>
                          <div className="fixed inset-0 z-10" onClick={() => setOpenTeamDropdownId(null)}></div>
                          <div className="absolute left-6 top-full z-20 mt-1 w-64 rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
                            <div className="mb-2 px-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Assign Team Members</div>
                            <div className="max-h-48 overflow-y-auto custom-scrollbar">
                              {assignableEmployees?.map(emp => {
                                const isAssigned = proj.employees.some(e => e.id === emp.id);
                                return (
                                  <label key={emp.id} className="flex cursor-pointer items-center gap-3 rounded p-2 hover:bg-slate-50">
                                    <input 
                                      type="checkbox" 
                                      checked={isAssigned}
                                      onChange={(e) => {
                                        const currentEmployeeIds = proj.employees.filter((e: any) => e.role === 'employee' || e.role === 'Employee').map((e: any) => e.id);
                                        const newEmployeeIds = e.target.checked 
                                          ? [...currentEmployeeIds, emp.id]
                                          : currentEmployeeIds.filter(id => id !== emp.id);
                                        handleUpdateProjectInline(proj, undefined, newEmployeeIds);
                                      }}
                                      className="h-4 w-4 rounded border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                                    />
                                    <div className="text-sm font-medium text-slate-700">{emp.name}</div>
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        </>
                      )}
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600">
                      {proj.task_count} tasks
                    </td>
                    <td className="px-6 py-4">
                      {proj.billing_type === 'fixed' ? (
                        <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#8B5CF6] border border-[#8B5CF6]">
                          {proj.fixed_hours} Hours
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#14B8A6] border border-[#14B8A6]">
                          Free Time
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600">
                      {formatDate(proj.deadline)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => openEditDrawer(proj)} className="rounded bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-600 transition hover:bg-blue-100">
                          Edit
                        </button>
                        <button onClick={() => handleDelete(proj.id)} className="rounded bg-rose-50 px-3 py-1.5 text-xs font-bold text-rose-600 transition hover:bg-rose-100">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {projects.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-20 text-center border-t-0">
                      <p className="text-slate-500 font-medium">No projects found matching the criteria.</p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200 pt-6">
            <p className="text-sm font-semibold text-slate-500">
              Page <span className="text-slate-800">{page}</span> of <span className="text-slate-800">{totalPages}</span>
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Drawer Overlay & Container */}
      <div className={`fixed inset-0 z-50 overflow-hidden ${isDrawerOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        <div 
          className={`absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-300 ${isDrawerOpen ? 'opacity-100' : 'opacity-0'}`} 
          onClick={closeDrawer} 
        />
        <div className={`absolute inset-y-0 right-0 w-full max-w-xl bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isDrawerOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="flex h-full flex-col">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
              <div>
                <h2 className="text-xl font-black text-slate-800">
                  {drawerMode === 'create' ? 'Create New Project' : 'Edit Project'}
                </h2>
                <p className="mt-1 text-sm font-semibold text-slate-500">
                  {drawerMode === 'create' ? 'Setup details, team, and budget' : 'Modify project settings'}
                </p>
              </div>
              <button onClick={closeDrawer} className="rounded-full p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-600 transition">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto p-6">
              <form id="project-form" onSubmit={handleSaveProject} className="space-y-8">
                
                {/* 1. Basic Details */}
                <div>
                  <h3 className="mb-4 text-xs font-black uppercase tracking-widest text-[#3B82F6]">Basic Details</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Project Name</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. Website Redesign"
                        value={formName}
                        onChange={e => setFormName(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Description</label>
                      <textarea
                        rows={3}
                        placeholder="Brief overview of the project..."
                        value={formDescription}
                        onChange={e => setFormDescription(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] resize-none"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Leader</label>
                        <select
                          value={formLeader}
                          onChange={e => setFormLeader(e.target.value)}
                          className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                        >
                          <option value="">Unassigned</option>
                          {assignableLeaders?.map(l => (
                            <option key={l.id} value={l.id}>{l.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Deadline</label>
                        <input
                          type="date"
                          value={formDeadline}
                          onChange={e => setFormDeadline(e.target.value)}
                          className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Status</label>
                      <select
                        value={formStatusId}
                        onChange={e => setFormStatusId(Number(e.target.value))}
                        className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                      >
                        {metadata?.project_statuses?.map(s => (
                          <option key={s.id} value={s.id}>{s.project_status}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* 2. Team Composition */}
                <div>
                  <h3 className="mb-4 text-xs font-black uppercase tracking-widest text-[#3B82F6]">Team Setup</h3>
                  <div className="space-y-4">
                    <div className="relative">
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Project Members</label>
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
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>

                      {isEmpDropdownOpen && (
                        <div className="absolute z-10 mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
                          <div className="max-h-48 overflow-y-auto custom-scrollbar">
                            {assignableEmployees?.map(emp => (
                              <label key={emp.id} className="flex cursor-pointer items-center gap-3 rounded p-2 hover:bg-slate-50">
                                <input 
                                  type="checkbox" 
                                  checked={formEmployees.includes(emp.id)}
                                  onChange={(e) => {
                                    if (e.target.checked) setFormEmployees([...formEmployees, emp.id]);
                                    else {
                                      setFormEmployees(formEmployees.filter(id => id !== emp.id));
                                    }
                                  }}
                                  className="h-4 w-4 rounded border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6]"
                                />
                                <div className="text-sm font-medium text-slate-700">{emp.name} <span className="text-xs text-slate-400">({emp.role})</span></div>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 3. Budget & Billing */}
                <div>
                  <h3 className="mb-4 text-xs font-black uppercase tracking-widest text-[#3B82F6]">Budget & Billing</h3>
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <label className={`flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg border-2 p-3 transition ${formBillingType === 'fixed' ? 'border-[#3B82F6] bg-blue-50 text-[#3B82F6]' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'}`}>
                        <input
                          type="radio"
                          name="billingType"
                          value="fixed"
                          checked={formBillingType === 'fixed'}
                          onChange={() => setFormBillingType('fixed')}
                          className="sr-only"
                        />
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        <span className="text-sm font-bold">Fixed Hours</span>
                      </label>
                      <label className={`flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg border-2 p-3 transition ${formBillingType === 'free' ? 'border-[#14B8A6] bg-teal-50 text-[#14B8A6]' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'}`}>
                        <input
                          type="radio"
                          name="billingType"
                          value="free"
                          checked={formBillingType === 'free'}
                          onChange={() => { setFormBillingType('free'); setFormBillingHours(''); }}
                          className="sr-only"
                        />
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
                        <span className="text-sm font-bold">Free Time</span>
                      </label>
                    </div>

                    {formBillingType === 'fixed' && (
                      <div className="animate-in fade-in slide-in-from-top-2">
                        <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Hour Budget</label>
                        <div className="relative">
                          <input
                            type="number"
                            min="1"
                            required
                            placeholder="e.g. 100"
                            value={formBillingHours}
                            onChange={e => setFormBillingHours(e.target.value)}
                            className="w-full rounded-lg border border-slate-300 px-4 py-2.5 pl-10 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
                          />
                          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-bold text-slate-400">#</span>
                        </div>
                        <p className="mt-1.5 text-[11px] font-semibold text-slate-500">Project tracking will be capped at this many hours.</p>
                      </div>
                    )}
                  </div>
                </div>

              </form>
            </div>

            {/* Drawer Footer */}
            <div className="border-t border-slate-100 bg-slate-50 p-6 flex gap-3">
              <button
                type="button"
                onClick={closeDrawer}
                className="flex-1 rounded-lg border border-slate-200 bg-white py-3 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                form="project-form"
                className={`flex-1 rounded-lg py-3 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
              >
                {drawerMode === 'create' ? 'Create Project' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </V2Shell>
  );
};
