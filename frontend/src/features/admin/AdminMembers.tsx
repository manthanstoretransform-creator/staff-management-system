import React, { useState, useMemo } from 'react';
import { V2Shell } from '../dashboard/v2/V2Shell';
import { 
  useGetMembersQuery, 
  useCreateMemberMutation, 
  useUpdateMemberMutation, 
  useDeleteMemberMutation,
} from '../../store/api/membersApi';
import type { Member } from '../../store/api/membersApi';
import { useFeedback } from '../../components/FeedbackProvider';
import { InlineRefreshIndicator } from '../../components/InlineRefreshIndicator';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

const GRADIENT_CYAN_PURPLE = 'bg-gradient-to-r from-[#0ea5e9] via-[#3b82f6] to-[#8b5cf6]';

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  if ((status || '').toLowerCase() === 'active') {
    return <span className="inline-flex items-center rounded-md bg-emerald-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-emerald-600 border border-emerald-200">Active</span>;
  }
  return <span className="inline-flex items-center rounded-md bg-slate-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-slate-500 border border-slate-200">Inactive</span>;
};

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '-';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const day = String(date.getDate()).padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short' });
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
};

const LoadingSpinner: React.FC = () => (
  <div className="flex min-h-28 items-center justify-center" role="status" aria-label="Loading">
    <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
  </div>
);

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
      <div>Showing {startItem} to {endItem} of {totalItems} members</div>
      <div className="flex items-center gap-3">
        <select value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setPage(1); }} className="rounded-md border border-slate-300 py-1.5 pl-3 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
          <option value={12}>12</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
        <div className="flex items-center gap-1">
          <button disabled={page === 1} onClick={() => setPage(page - 1)} className="flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100 disabled:opacity-30" aria-label="Previous page">&larr;</button>
          {pages.map((visiblePage, index) => visiblePage === '...' ? (
            <span key={`ellipsis-${index}`} className="flex h-8 w-8 items-center justify-center text-slate-400">...</span>
          ) : (
            <button key={visiblePage} onClick={() => setPage(visiblePage as number)} className={`flex h-8 w-8 items-center justify-center rounded text-sm font-semibold transition ${visiblePage === page ? 'bg-blue-500 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'}`}>{visiblePage}</button>
          ))}
          <button disabled={page === totalPages} onClick={() => setPage(page + 1)} className="flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100 disabled:opacity-30" aria-label="Next page">&rarr;</button>
        </div>
      </div>
    </div>
  );
};


const MemberProfileView: React.FC<{ member: Member }> = ({ member }) => {
  const recentActivity = [
    { id: 1, action: 'Clocked Out', project: 'Hubstaff to Monitra', time: 'Today, 6:00 PM', color: 'bg-rose-500' },
    { id: 2, action: 'Clocked In', project: 'Hubstaff to Monitra', time: 'Today, 9:00 AM', color: 'bg-emerald-500' },
    { id: 3, action: 'Completed Task', project: 'Website Redesign', time: 'Yesterday, 4:30 PM', color: 'bg-blue-500' },
    { id: 4, action: 'Joined Team', project: 'Mobile App', time: 'Monday, 10:00 AM', color: 'bg-purple-500' },
  ];

  const assignedProjects = [
    { id: 1, name: 'Hubstaff to Monitra', role: 'Developer', progress: 75, color: 'bg-blue-500' },
    { id: 2, name: 'Website Redesign', role: 'Lead', progress: 40, color: 'bg-emerald-500' },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-20">
      
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left Column: Profile Card & Stats */}
        <div className="w-full md:w-1/3 space-y-6">
          {/* Profile Card */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm text-center">
            <div className={`mx-auto flex h-20 w-20 items-center justify-center rounded-2xl text-2xl font-bold text-white shadow-md ${GRADIENT_CYAN_PURPLE}`}>
              {(member.name || 'U').substring(0, 2).toUpperCase()}
            </div>
            <h2 className="mt-4 text-xl font-black text-slate-800">{member.name}</h2>
            <p className="text-sm font-semibold text-slate-500">{member.designation || member.role}</p>
            <div className="mt-4 flex justify-center gap-2">
              <span className="inline-flex items-center rounded-md bg-emerald-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-emerald-600 border border-emerald-200">Active</span>
              <span className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 text-[11px] font-bold tracking-wider text-slate-600 border border-slate-200 uppercase">{member.role}</span>
            </div>
            <div className="mt-6 border-t border-slate-100 pt-4 text-left space-y-3">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Email</div>
                <div className="text-sm font-semibold text-slate-700">{member.email}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Joined</div>
                <div className="text-sm font-semibold text-slate-700">{formatDate(member.date_of_joining)}</div>
              </div>
            </div>
          </div>

          {/* Weekly Stats */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-4">This Week</h3>
            <div className="flex items-end justify-between mb-2">
              <div className="text-3xl font-black text-slate-700">34<span className="text-lg text-slate-400">h</span> 12<span className="text-lg text-slate-400">m</span></div>
              <div className="text-xs font-bold text-emerald-500 bg-emerald-50 px-2 py-1 rounded-md">+4%</div>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-blue-500 w-[85%] rounded-full"></div>
            </div>
            <div className="mt-2 text-right text-[10px] font-bold text-slate-400">Goal: 40h</div>
          </div>
        </div>

        {/* Right Column: Projects & Activity */}
        <div className="w-full md:w-2/3 space-y-6">
          {/* Projects */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-4">Assigned Projects</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {assignedProjects.map(p => (
                <div key={p.id} className="rounded-xl border border-slate-100 bg-slate-50 p-4 transition hover:shadow-md">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="font-bold text-slate-700">{p.name}</div>
                      <div className="text-xs font-medium text-slate-500">{p.role}</div>
                    </div>
                    <div className={`h-8 w-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${p.color}`}>
                      {p.name.charAt(0)}
                    </div>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-slate-200 overflow-hidden">
                    <div className={`h-full ${p.color}`} style={{width: p.progress + '%'}}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 mb-6">Recent Activity</h3>
            <div className="space-y-6 pl-2">
              {recentActivity.map((act, i) => (
                <div key={act.id} className="relative pl-6">
                  <div className={`absolute left-[-5px] top-1 h-3 w-3 rounded-full border-2 border-white shadow-sm ${act.color}`}></div>
                  {i !== recentActivity.length - 1 && (
                    <div className="absolute left-0 top-4 bottom-[-24px] w-[2px] bg-slate-100"></div>
                  )}
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold text-slate-700 text-sm">{act.action}</div>
                      <div className="text-xs font-medium text-slate-500">{act.project}</div>
                    </div>
                    <div className="text-[11px] font-bold text-slate-400">{act.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export const AdminMembers: React.FC = () => {
  const { showToast, confirmAction } = useFeedback();
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);

  const [search, setSearch] = useState('');
  const [filterRole, setFilterRole] = useState('All');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // One request for the finished search term instead of one per keystroke.
  const debouncedSearch = useDebouncedValue(search);

  const { data, isLoading, isFetching, isError } = useGetMembersQuery({
    page,
    limit: pageSize,
    role: filterRole,
    status: 'All',
    search: debouncedSearch,
  });

  // Only block on the very first load. Once rows are on screen a refetch runs
  // behind them, and mutations are applied to the cache optimistically, so
  // there is nothing left to wait for.
  const showFirstLoad = isLoading && !data;
  const isRevalidating = isFetching && !showFirstLoad;
  
  const [createMember] = useCreateMemberMutation();
  const [updateMember, { isLoading: isUpdatingMember }] = useUpdateMemberMutation();
  const [deleteMember, { isLoading: isDeletingMember }] = useDeleteMemberMutation();

  // Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create');
  const [editingId, setEditingId] = useState<number | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formRole, setFormRole] = useState('employee');
  const [formStatus, setFormStatus] = useState('active');
  const [formDOJ, setFormDOJ] = useState('');
  const [formDOB, setFormDOB] = useState('');
  const [formDesignation, setFormDesignation] = useState('');

  const openCreateDrawer = () => {
    setDrawerMode('create');
    setEditingId(null);
    setFormName('');
    setFormEmail('');
    setFormRole('employee');
    setFormStatus('active');
    setFormDOJ('');
    setFormDOB('');
    setFormDesignation('');
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (member: Member) => {
    setDrawerMode('edit');
    setEditingId(member.id);
    setFormName(member.name);
    setFormEmail(member.email);
    setFormRole(member.role);
    setFormStatus(member.status);
    setFormDOJ(member.date_of_joining || '');
    setFormDOB(member.date_of_birth || '');
    setFormDesignation(member.designation || '');
    setIsDrawerOpen(true);
  };

  const handleSaveMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName || !formEmail) return;

    const payload = {
      name: formName,
      email: formEmail,
      role: formRole,
      status: formStatus,
      date_of_joining: formDOJ || null,
      date_of_birth: formDOB || null,
      designation: formDesignation,
    };

    try {
      if (drawerMode === 'create') {
        await createMember(payload).unwrap();
      } else if (drawerMode === 'edit' && editingId) {
        await updateMember({ id: editingId, body: payload }).unwrap();
      }
      setIsDrawerOpen(false);
      showToast(drawerMode === 'create' ? 'Member created successfully.' : 'Member updated successfully.', 'success');
    } catch (err) {
      console.error('Failed to save member', err);
      showToast('Unable to save member. Please try again.', 'error');
    }
  };

  const handleDeleteMember = async (id: number) => {
    if (await confirmAction('Delete member?', 'This member will be permanently removed from the directory.')) {
      try {
        await deleteMember(id).unwrap();
        showToast('Member deleted successfully.', 'success');
      } catch (err) {
        console.error('Failed to delete member', err);
        showToast('Unable to delete member. Please try again.', 'error');
      }
    }
  };

  const filteredItems = useMemo(() => {
    return data?.items || [];
  }, [data?.items]);

  const totalPages = data?.pages || 1;


  const selectedMember = selectedProfileId ? data?.items?.find(m => m.id === selectedProfileId) : null;

  if (selectedMember) {
    return (
      <V2Shell
        title="Member Profile"
        subtitle="View detailed activity, assigned projects, and statistics."
        actions={
          <button
            onClick={() => setSelectedProfileId(null)}
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7"/></svg>
            Back to Directory
          </button>
        }
      >
        <MemberProfileView member={selectedMember} />
      </V2Shell>
    );
  }

  return (
    <V2Shell
      title="Members Directory"
      subtitle="Manage employees, their roles, and company details."
      actions={
        <div className="flex gap-2">
          <button
            onClick={openCreateDrawer}
            className={`rounded-lg px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
          >
            + Add Member
          </button>
        </div>
      }
    >
      <div className="mx-auto max-w-7xl space-y-6 pb-20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-1 items-center gap-2 px-2">
            <svg className="h-5 w-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search members by name or email..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 text-slate-700"
            />
          </div>
          
          <div className="h-8 w-px bg-slate-200 hidden lg:block"></div>

          <div className="flex items-center gap-3 pr-2">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">ROLE:</span>
            <select
              value={filterRole}
              onChange={(e) => { setFilterRole(e.target.value); setPage(1); }}
              className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none focus:border-[#38bdf8] hover:bg-slate-50 shadow-sm"
            >
              <option value="All">All Roles</option>
              <option value="admin">Admin</option>
              <option value="leader">Leader</option>
              <option value="employee">Employee</option>
            </select>
          </div>
        </div>

        <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="pointer-events-none absolute right-3 top-3 z-10">
            <InlineRefreshIndicator active={isRevalidating || isUpdatingMember || isDeletingMember} />
          </div>
          <div className="overflow-x-auto pb-4">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Employee</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Role</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Designation</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Date of Joining</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Date of Birth</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px] text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {showFirstLoad ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-8">
                      <LoadingSpinner />
                    </td>
                  </tr>
                ) : isError ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-red-500">
                      Failed to fetch members. Please try again.
                    </td>
                  </tr>
                ) : filteredItems.length > 0 ? (
                  filteredItems.map(member => (
                    <tr key={member.id} className="transition hover:bg-slate-50/50">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white shadow-sm ${GRADIENT_CYAN_PURPLE}`}>
                            {(member.name || 'U').substring(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="font-bold text-slate-800 truncate cursor-pointer hover:text-blue-600 hover:underline transition" onClick={() => setSelectedProfileId(member.id)}>{member.name || '-'}</div>
                            <div className="text-xs text-slate-500 truncate mt-0.5">{member.email || '-'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold ${
                          member.role === 'admin' ? 'text-purple-600' :
                          member.role === 'leader' ? 'text-blue-600' :
                          'text-slate-600'
                        }`}>
                          {(member.role || '').charAt(0).toUpperCase() + (member.role || '').slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={member.status} />
                      </td>
                      <td className="px-6 py-4 font-medium text-slate-600">{member.designation || '-'}</td>
                      <td className="px-6 py-4 font-medium text-slate-600">{formatDate(member.date_of_joining)}</td>
                      <td className="px-6 py-4 font-medium text-slate-600">{formatDate(member.date_of_birth)}</td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => openEditDrawer(member)}
                            className="rounded px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-[#14B8A6] border border-[#14B8A6]/30 transition hover:bg-[#14B8A6]/10"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteMember(member.id)}
                            className="rounded px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-rose-500 border border-rose-200 transition hover:bg-rose-50"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      No members found matching your criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
        </div>
        {totalPages > 1 && (
          <Pagination page={page} totalPages={totalPages} totalItems={data?.total || 0} limit={pageSize} setPage={setPage} setLimit={setPageSize} />
        )}
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
                {drawerMode === 'create' ? 'Add New Member' : 'Edit Member'}
              </h3>
              <button type="button" onClick={() => setIsDrawerOpen(false)} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <form id="member-form" onSubmit={handleSaveMember} className="p-6 space-y-6">
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Employee Name</label>
                  <input
                    required
                    type="text"
                    value={formName}
                    onChange={e => setFormName(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    placeholder="E.g. John Doe"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Email Address</label>
                  <input
                    required
                    type="email"
                    value={formEmail}
                    onChange={e => setFormEmail(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    placeholder="john.doe@company.com"
                  />
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Role</label>
                    <select
                      required
                      value={formRole}
                      onChange={e => setFormRole(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium bg-white"
                    >
                      <option value="employee">Employee</option>
                      <option value="leader">Leader</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Status</label>
                    <select
                      required
                      value={formStatus}
                      onChange={e => setFormStatus(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium bg-white"
                    >
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 pt-2 border-t border-slate-100">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Designation</label>
                    <input
                      type="text"
                      value={formDesignation}
                      onChange={e => setFormDesignation(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium text-slate-700"
                      placeholder="e.g. Full Stack Developer"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Date of Joining</label>
                    <input
                      type="date"
                      value={formDOJ}
                      onChange={e => setFormDOJ(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium text-slate-700"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Date of Birth</label>
                    <input
                      type="date"
                      value={formDOB}
                      onChange={e => setFormDOB(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium text-slate-700"
                    />
                  </div>
                </div>
              </form>
            </div>
            
            <div className="border-t border-slate-100 p-6 bg-slate-50">
              <button
                type="submit"
                form="member-form"
                className={`w-full rounded-lg px-6 py-3 text-sm font-bold text-white shadow-md hover:opacity-90 transition-opacity ${GRADIENT_CYAN_PURPLE}`}
              >
                {drawerMode === 'create' ? 'Save Member' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </V2Shell>
  );
};
