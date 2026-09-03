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
  type Project
} from '../../store/api/projectsApi';
import { useFeedback } from '../../components/FeedbackProvider';
import { InlineRefreshIndicator } from '../../components/InlineRefreshIndicator';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { PaginationArrow } from '../../components/PaginationArrow';

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

const Pagination: React.FC<{
  page: number;
  totalPages: number;
  totalItems: number;
  limit: number;
  setPage: (page: number) => void;
  setLimit: (limit: number) => void;
}> = ({ page, totalPages, totalItems, limit, setPage, setLimit }) => {
  const startItem = totalItems === 0 ? 0 : (page - 1) * limit + 1;
  const endItem = Math.min(page * limit, totalItems);
  const pages = totalPages <= 7
    ? Array.from({ length: totalPages }, (_, index) => index + 1)
    : page <= 4
      ? [1, 2, 3, 4, 5, '...', totalPages]
      : page >= totalPages - 3
        ? [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages]
        : [1, '...', page - 1, page, page + 1, '...', totalPages];

  return (
    <div className="mt-8 flex flex-col items-center justify-between gap-4 border-t border-slate-200 pt-5 text-sm text-slate-500 sm:flex-row">
      <div>Showing {startItem} to {endItem} of {totalItems} projects</div>
      <div className="flex items-center gap-3">
        <select
          value={limit}
          onChange={(e) => { setLimit(Number(e.target.value)); setPage(1); }}
          className="rounded-md border border-slate-300 py-1.5 pl-3 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value={12}>12</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
        <div className="flex items-center gap-1">
          <PaginationArrow direction="prev" disabled={page === 1} onClick={() => setPage(page - 1)} />
          {pages.map((visiblePage, index) => visiblePage === '...' ? (
            <span key={`ellipsis-${index}`} className="flex h-8 w-8 items-center justify-center text-slate-400">...</span>
          ) : (
            <button key={visiblePage} onClick={() => setPage(visiblePage as number)} className={`flex h-8 w-8 items-center justify-center rounded text-sm font-semibold transition ${visiblePage === page ? 'bg-blue-500 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'}`}>
              {visiblePage}
            </button>
          ))}
          <PaginationArrow direction="next" disabled={page === totalPages} onClick={() => setPage(page + 1)} />
        </div>
      </div>
    </div>
  );
};

const AssigneeSelector: React.FC<{
  selectedIds: number[];
  options: any[];
  onChange: (newIds: number[]) => void;
  isOpen: boolean;
  setIsOpen: (val: boolean) => void;
  onClose: () => void;
  label?: string;
}> = ({ selectedIds, options, onChange, isOpen, setIsOpen, onClose, label = "ASSIGN TO" }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const selectedMembers = (options || []).filter(o => (selectedIds || []).includes(o.id));
  const filteredOptions = (options || []).filter(o => (o.name || '').toLowerCase().includes(searchTerm.toLowerCase()));

  const getColor = (id: number) => {
    const colors = ['bg-blue-500', 'bg-rose-500', 'bg-emerald-500', 'bg-amber-500', 'bg-purple-500', 'bg-cyan-500'];
    return colors[id % colors.length];
  };

  return (
    <div className="relative">
      <div 
        className="flex items-center gap-1 cursor-pointer group"
        onClick={() => setIsOpen(!isOpen)}
      >
        {selectedMembers.length > 0 ? (
          <div className="flex -space-x-2 items-center p-1">
            {selectedMembers.slice(0, 3).map(m => (
              <div 
                key={m.id} 
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-2 ring-white text-white text-[10px] font-bold shadow-sm ${getColor(m.id)}`}
                title={m.name}
              >
                {(m.name || 'U').split(' ').map((n: string) => n[0]).join('').substring(0, 2).toUpperCase()}
              </div>
            ))}
            {selectedMembers.length > 3 && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-2 ring-white bg-slate-100 text-slate-500 text-[10px] font-bold shadow-sm">
                +{selectedMembers.length - 3}
              </div>
            )}
          </div>
        ) : (
          <button type="button" className="flex items-center justify-center h-8 w-8 rounded-full border border-dashed border-slate-300 text-slate-400 hover:text-slate-600 hover:border-slate-400 bg-slate-50 transition">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
          </button>
        )}
      </div>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={onClose}></div>
          <div className="absolute left-0 top-full z-20 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-2xl">
            <div className="mb-2 px-1 text-[11px] font-black uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mb-3 px-1">
              <input 
                type="text" 
                placeholder="Search members..." 
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 outline-none transition focus:border-blue-500 focus:bg-white"
              />
            </div>
            <div className="max-h-60 overflow-y-auto custom-scrollbar pr-1">
              {filteredOptions.length > 0 ? filteredOptions.map(emp => {
                const isSelected = selectedIds.includes(emp.id);
                return (
                  <label key={emp.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg p-2 hover:bg-slate-50 transition">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`shrink-0 flex h-8 w-8 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm ${getColor(emp.id)}`}>
                        {(emp.name || 'U').split(' ').map((n: string) => n[0]).join('').substring(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0 flex flex-col">
                        <span className="truncate text-sm font-bold text-slate-700">{emp.name}</span>
                        <span className="truncate text-[10px] font-semibold text-slate-400">{emp.role}</span>
                      </div>
                    </div>
                    <div className="shrink-0 flex items-center justify-center">
                      <input 
                        type="checkbox" 
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) onChange([...selectedIds, emp.id]);
                          else onChange(selectedIds.filter(id => id !== emp.id));
                        }}
                        className="h-4 w-4 rounded border-slate-300 text-blue-500 focus:ring-blue-500" 
                      />
                    </div>
                  </label>
                );
              }) : (
                <div className="py-4 text-center text-xs text-slate-500">No members found.</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};


const StatusPillDropdown = ({
  value,
  options,
  onChange,
  className = "",
  fullWidth = false
}: {
  value: number | undefined;
  options: { id: number; project_status: string; color: string }[];
  onChange: (val: number) => void;
  className?: string;
  fullWidth?: boolean;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const selected = options?.find((o) => o.id === value) || options?.[0];

  return (
    <div className={`relative ${fullWidth ? 'block w-full' : 'inline-block'} ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-[12px] font-bold tracking-wide transition shadow-sm border ${fullWidth ? 'w-full px-4' : 'px-3 py-1.5 text-[11px]'}`}
        style={{ 
          color: selected?.color || '#334155', 
          backgroundColor: `${selected?.color || '#334155'}15`,
          borderColor: `${selected?.color || '#334155'}30`
        }}
      >
        <span>{selected?.project_status || 'Select Status'}</span>
        <svg className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)}></div>
          <div className={`absolute left-0 top-full z-20 mt-1.5 rounded-xl border border-slate-100 bg-white p-2 shadow-xl ${fullWidth ? 'w-full' : 'w-40'}`}>
            <div className="flex flex-col gap-1.5">
              {(options || []).map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    onChange(opt.id);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left rounded-md transition border border-transparent hover:brightness-95 ${fullWidth ? 'px-4 py-2 text-[12px]' : 'px-3 py-1.5 text-[11px]'} font-bold`}
                  style={{
                    color: opt.color,
                    backgroundColor: `${opt.color}15`,
                    borderColor: value === opt.id ? `${opt.color}40` : 'transparent'
                  }}
                >
                  {opt.project_status}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

type ColumnKey = 'project' | 'status' | 'leader' | 'team' | 'tasks' | 'billing' | 'deadline' | 'manage';
const COLUMNS: { key: ColumnKey; label: string }[] = [
  { key: 'project', label: 'Project' },
  { key: 'status', label: 'Status' },
  { key: 'leader', label: 'Leader' },
  { key: 'team', label: 'Team' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'billing', label: 'Billing' },
  { key: 'deadline', label: 'Deadline' },
  { key: 'manage', label: 'Manage' },
];

export const AdminProjectManagement: React.FC = () => {
  const { showToast, confirmAction } = useFeedback();
  const [search, setSearch] = useState('');
  const [filterStatusId, setFilterStatusId] = useState<number | null>(null);

  const [visibleColumns, setVisibleColumns] = useState<Record<ColumnKey, boolean>>({
    project: true, status: true, leader: true, team: true, tasks: true, billing: true, deadline: true, manage: true
  });
  const [showColumnDropdown, setShowColumnDropdown] = useState(false);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [viewingProject, setViewingProject] = useState<Project | null>(null);

  // RTK Query Hooks
  const { data: metadata } = useGetProjectMetadataQuery();
  const { data: assignableLeaders } = useGetAssignableLeadersQuery();
  const { data: assignableEmployees } = useGetAssignableEmployeesQuery();
  // One request for the finished search term instead of one per keystroke.
  const debouncedSearch = useDebouncedValue(search);

  const { data: projectsData, isLoading, isFetching } = useGetProjectsQuery({
    page,
    limit: pageSize,
    search: debouncedSearch,
    status_id: filterStatusId,
  });
  
  const [createProject] = useCreateProjectMutation();
  const [updateProject, { isLoading: isUpdatingProject }] = useUpdateProjectMutation();
  const [deleteProject] = useDeleteProjectMutation();

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
    setFormEmployees((proj.employees || []).filter(e => e.role === 'employee' || e.role === 'Employee').map(e => e.id));
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
        // Seeding a new project's starter tasks is the backend's job
        // (`DEFAULT_PROJECT_TASKS` in project_management.py), and it already
        // happens inside the same transaction that creates the project. This
        // screen used to add its own four on top, once per assigned employee,
        // so a project opened with eight tasks for one employee and twelve for
        // two. One owner for the defaults; the client just creates the project.
        await createProject(payload).unwrap();
      } else if (drawerMode === 'edit' && editingId) {
        await updateProject({ id: editingId, body: payload }).unwrap();
      }
      closeDrawer();
      showToast(drawerMode === 'create' ? 'Project created successfully.' : 'Project updated successfully.', 'success');
    } catch (err) {
      console.error("Failed to save project:", err);
      showToast('Unable to save project. Please try again.', 'error');
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
          : (proj.employees || []).filter((e: any) => e.role === 'employee' || e.role === 'Employee').map((e: any) => e.id),
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
  const [openManageDropdownId, setOpenManageDropdownId] = useState<number | null>(null);

  const handleDelete = async (id: number) => {
    if (await confirmAction('Delete project?', 'This project and its management record will be permanently removed.')) {
      try {
        await deleteProject(id).unwrap();
        showToast('Project deleted successfully.', 'success');
      } catch (err) {
        console.error("Failed to delete project:", err);
        showToast('Unable to delete project. Please try again.', 'error');
      }
    }
  };

  const handleExport = () => {
    const headers = ['Project', 'Status', 'Leader', 'Members', 'Tasks', 'Billing', 'Deadline'];
    const escapeCsv = (value: string | number | null | undefined) => `"${String(value ?? '').replace(/"/g, '""')}"`;
    const rows = projects.map((project) => [
      project.project_name,
      project.status?.name,
      project.leader?.name || 'Unassigned',
      project.employee_count,
      project.task_count,
      project.billing_type === 'fixed' ? `${project.fixed_hours || 0} Hours` : 'Free Time',
      project.deadline || 'No Deadline',
    ]);
    const csv = [headers, ...rows].map((row) => row.map(escapeCsv).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'projects.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const projects = projectsData?.items || [];
  const totalPages = projectsData?.pagination?.total_pages || 1;

  // Block only until the table has something in it. After that, refetches run
  // behind the rows and edits are applied to the cache optimistically.
  const showFirstLoad = isLoading && !projectsData;
  const isRevalidating = isFetching && !showFirstLoad;

  return (
    <V2Shell
      title="Project Management"
      subtitle="Manage projects, deadlines, team assignments, and client billing."
      actions={
          <div className="flex items-center gap-4">
            <InlineRefreshIndicator active={isRevalidating || isUpdatingProject} />
            <button
              onClick={openCreateDrawer}
          className={`rounded-lg px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
        >
          + Create Project
        </button>
          </div>
      }
    >
      <div className="w-full space-y-8 pb-20">
        
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
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6] focus:bg-white focus:ring-1 focus:ring-[#3B82F6]"
            />
          </div>

          <div className="flex w-full sm:w-auto items-center gap-3">
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowColumnDropdown(!showColumnDropdown)}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 flex items-center gap-2"
              >
                Columns
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showColumnDropdown && (
                <div className="absolute right-0 mt-2 w-48 rounded-xl bg-white p-3 shadow-xl border border-slate-100 z-50">
                  <div className="text-xs font-bold text-slate-400 mb-3 uppercase tracking-wider">Visible Columns</div>
                  <div className="space-y-2">
                    {COLUMNS.map(col => (
                      <label key={col.key} className="flex items-center gap-3 cursor-pointer group">
                        <input 
                          type="checkbox" 
                          checked={visibleColumns[col.key]} 
                          onChange={() => setVisibleColumns(prev => ({...prev, [col.key]: !prev[col.key]}))} 
                          className="h-4 w-4 rounded border-slate-300 text-[#3B82F6] focus:ring-[#3B82F6] transition" 
                        />
                        <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900 transition">{col.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            <button
              type="button"
              onClick={handleExport}
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
            >
              Export
            </button>
            <StatusPillDropdown
                value={filterStatusId || 0}
                options={[
                  { id: 0, project_status: 'All Statuses', color: '#64748b' },
                  ...(metadata?.project_statuses || [])
                ]}
                onChange={(val) => setFilterStatusId(val === 0 ? null : val)}
                className="w-full sm:w-auto min-h-[38px] flex items-center"
              />
          </div>
        </div>

        {/* Project Cards Grid */}
        {showFirstLoad ? (
          <div className="flex justify-center p-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
          </div>
        ) : (
          <div className="relative overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  {visibleColumns.project && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Project</th>}
                  {visibleColumns.status && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Status</th>}
                  {visibleColumns.leader && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Leader</th>}
                  {visibleColumns.team && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Team</th>}
                  {visibleColumns.tasks && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Tasks</th>}
                  {visibleColumns.billing && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Billing</th>}
                  {visibleColumns.deadline && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Deadline</th>}
                  {visibleColumns.manage && <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Manage</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {projects.map(proj => (
                  <tr key={proj.id} className="group transition hover:bg-slate-50/80">
                    {visibleColumns.project && <td className="px-6 py-4">
                      <div className="font-bold text-slate-800">{proj.project_name}</div>
                      {proj.description && <div className="text-xs text-slate-500 truncate max-w-[200px]">{proj.description}</div>}
                    </td>}
                    {visibleColumns.status && <td className="px-6 py-4 overflow-visible">
                      <StatusPillDropdown
                        value={proj.status?.id}
                        options={metadata?.project_statuses || []}
                        onChange={(val) => handleUpdateProjectInline(proj, val, undefined)}
                      />
                    </td>}
                    {visibleColumns.leader && <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm ${GRADIENT_CYAN_PURPLE}`}>
                          {(proj.leader?.name || 'U').substring(0, 2).toUpperCase()}
                        </div>
                        <div className="font-semibold text-slate-700">{proj.leader?.name || 'Unassigned'}</div>
                      </div>
                    </td>}
                    {visibleColumns.team && <td className="px-6 py-4 font-medium text-slate-600 relative overflow-visible">
                      <AssigneeSelector
                        selectedIds={(proj.employees || []).filter((e: any) => e.role === 'employee' || e.role === 'Employee').map((e: any) => e.id)}
                        options={assignableEmployees || []}
                        onChange={(newIds) => handleUpdateProjectInline(proj, undefined, newIds)}
                        isOpen={openTeamDropdownId === proj.id}
                        setIsOpen={(open) => setOpenTeamDropdownId(open ? proj.id : null)}
                        onClose={() => setOpenTeamDropdownId(null)}
                      />
                    </td>}
                    {visibleColumns.tasks && <td className="px-6 py-4 font-medium text-slate-600">
                      {proj.task_count}
                    </td>}
                    {visibleColumns.billing && <td className="px-6 py-4">
                      {proj.billing_type === 'fixed' ? (
                        <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#8B5CF6] border border-[#8B5CF6]">
                          {proj.fixed_hours} Hours
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#14B8A6] border border-[#14B8A6]">
                          Free Time
                        </span>
                      )}
                    </td>}
                    {visibleColumns.deadline && <td className="px-6 py-4 font-medium text-slate-600">
                      {formatDate(proj.deadline)}
                    </td>}
                    {visibleColumns.manage && <td className="relative px-6 py-4">
                      <button onClick={() => setOpenManageDropdownId(openManageDropdownId === proj.id ? null : proj.id)} className="flex items-center gap-2 rounded bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700 transition hover:bg-slate-200">
                        Manage
                        <svg className="h-3 w-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                      </button>
                      {openManageDropdownId === proj.id && (
                        <>
                          <div className="fixed inset-0 z-10" onClick={() => setOpenManageDropdownId(null)} />
                          <div className="absolute right-6 z-20 mt-1 w-32 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl">
                            <button onClick={() => { setViewingProject(proj); setOpenManageDropdownId(null); }} className="block w-full px-3 py-2 text-left text-xs font-bold text-indigo-600 transition hover:bg-indigo-50">View</button>
                            <button onClick={() => { openEditDrawer(proj); setOpenManageDropdownId(null); }} className="block w-full px-3 py-2 text-left text-xs font-bold text-blue-600 transition hover:bg-blue-50">Edit</button>
                            <button onClick={() => { handleDelete(proj.id); setOpenManageDropdownId(null); }} className="block w-full px-3 py-2 text-left text-xs font-bold text-rose-600 transition hover:bg-rose-50">Delete</button>
                          </div>
                        </>
                      )}
                    </td>}
                  </tr>
                ))}
                {projects.length === 0 && (
                  <tr>
                    <td colSpan={Object.values(visibleColumns).filter(Boolean).length || 1} className="py-20 text-center border-t-0">
                      <p className="text-slate-500 font-medium">No projects found matching the criteria.</p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && <Pagination page={page} totalPages={totalPages} totalItems={projectsData?.pagination?.total || 0} limit={pageSize} setPage={setPage} setLimit={setPageSize} />}
      </div>

      {viewingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4 backdrop-blur-sm">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-100 bg-slate-50 px-6 py-5">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-black text-slate-800">{viewingProject.project_name}</h2>
                  <span className="rounded-md px-2.5 py-1 text-xs font-bold" style={{ color: viewingProject.status?.color, backgroundColor: `${viewingProject.status?.color || '#64748b'}15` }}>
                    {viewingProject.status?.name || 'Unknown'}
                  </span>
                </div>
                <p className="mt-1 text-sm font-semibold text-slate-500">Project details and assigned work</p>
              </div>
              <button type="button" onClick={() => setViewingProject(null)} className="rounded-lg p-2 text-slate-400 transition hover:bg-white hover:text-slate-700" aria-label="Close project details">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="max-h-[calc(90vh-86px)] overflow-y-auto p-6">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Leader</div>
                  <div className="mt-2 text-sm font-bold text-slate-800">{viewingProject.leader?.name || 'Unassigned'}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Team</div>
                  <div className="mt-2 text-sm font-bold text-slate-800">{viewingProject.employee_count} members</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Tasks</div>
                  <div className="mt-2 text-sm font-bold text-slate-800">{viewingProject.task_count} tasks</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Deadline</div>
                  <div className="mt-2 text-sm font-bold text-slate-800">{formatDate(viewingProject.deadline)}</div>
                </div>
              </div>

              <div className="mt-6 grid gap-6 md:grid-cols-2">
                <section>
                  <h3 className="text-xs font-black uppercase tracking-widest text-blue-500">Description</h3>
                  <p className="mt-3 rounded-xl border border-slate-100 bg-white p-4 text-sm leading-6 text-slate-600 shadow-sm">{viewingProject.description || 'No description provided.'}</p>
                </section>
                <section>
                  <h3 className="text-xs font-black uppercase tracking-widest text-blue-500">Billing</h3>
                  <p className="mt-3 rounded-xl border border-slate-100 bg-white p-4 text-sm font-semibold text-slate-700 shadow-sm">
                    {viewingProject.billing_type === 'fixed' ? `${viewingProject.fixed_hours || 0} fixed hours` : 'Free time billing'}
                  </p>
                </section>
              </div>

              <section className="mt-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-black uppercase tracking-widest text-blue-500">Tasks</h3>
                  <span className="text-xs font-bold text-slate-400">{viewingProject.tasks?.length || 0} listed</span>
                </div>
                <div className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200">
                  {viewingProject.tasks?.length ? viewingProject.tasks.map((task) => (
                    <div key={task.id} className="flex items-center justify-between gap-4 bg-white px-4 py-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-bold text-slate-800">{task.name}</div>
                        <div className="mt-1 text-xs font-medium text-slate-500">{task.assignee?.name || 'Unassigned'}</div>
                      </div>
                      <span className="shrink-0 rounded-md px-2 py-1 text-[10px] font-bold" style={{ color: task.status?.color, backgroundColor: `${task.status?.color || '#64748b'}15` }}>
                        {task.status?.name || 'Unknown'}
                      </span>
                    </div>
                  )) : <p className="px-4 py-6 text-center text-sm text-slate-500">No tasks assigned.</p>}
                </div>
              </section>
            </div>
          </div>
        </div>
      )}

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
                          <option value="" disabled hidden>Select the leader...</option>
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
                      <StatusPillDropdown
                        value={formStatusId}
                        options={metadata?.project_statuses || []}
                        onChange={(val) => setFormStatusId(val)}
                        fullWidth={true}
                      />
                    </div>
                  </div>
                </div>

                {/* 2. Team Composition */}
                <div>
                  <h3 className="mb-4 text-xs font-black uppercase tracking-widest text-[#3B82F6]">Team Setup</h3>
                  <div className="space-y-4">
                    <div className="relative">
                      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Project Members</label>
                      <div className="w-full rounded-lg border border-slate-300 px-4 py-1.5 bg-white shadow-sm min-h-[46px] flex items-center">
                        <AssigneeSelector
                          selectedIds={formEmployees}
                          options={assignableEmployees || []}
                          onChange={(newIds) => setFormEmployees(newIds)}
                          isOpen={isEmpDropdownOpen}
                          setIsOpen={(open) => setIsEmpDropdownOpen(open)}
                          onClose={() => setIsEmpDropdownOpen(false)}
                        />
                      </div>
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
