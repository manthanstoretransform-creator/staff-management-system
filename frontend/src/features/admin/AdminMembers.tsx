import React, { useState, useMemo } from 'react';
import { V2Shell } from '../dashboard/v2/V2Shell';

const GRADIENT_CYAN_PURPLE = 'bg-gradient-to-r from-[#0ea5e9] via-[#3b82f6] to-[#8b5cf6]';

type MemberRole = 'Admin' | 'Leader' | 'Employee';
type MemberStatus = 'Active' | 'Inactive';

type Member = {
  id: string;
  name: string;
  email: string;
  role: MemberRole;
  dateOfJoining: string;
  dateOfBirth: string;
  status: MemberStatus;
};

// Mock data generator
const generateMockMembers = (): Member[] => {
  const roles: MemberRole[] = ['Admin', 'Leader', 'Employee', 'Employee', 'Employee', 'Leader'];
  const firstNames = ['David', 'Eve', 'Frank', 'Grace', 'Henry', 'Ivy', 'Jack', 'Karen', 'Alice', 'Bob', 'Charlie'];
  const lastNames = ['Evans', 'Foster', 'Green', 'Hall', 'Ives', 'Jones', 'King', 'Lee', 'Cooper', 'Smith', 'Davis'];
  
  return Array.from({ length: 45 }).map((_, i) => {
    const fn = firstNames[i % firstNames.length];
    const ln = lastNames[i % lastNames.length];
    return {
      id: `m-${i + 1}`,
      name: `${fn} ${ln}`,
      email: `${fn.toLowerCase()}.${ln.toLowerCase()}@company.com`,
      role: roles[i % roles.length],
      dateOfJoining: `202${(i % 4) + 1}-0${(i % 9) + 1}-1${(i % 8) + 1}`,
      dateOfBirth: `199${(i % 9)}-0${(i % 9) + 1}-1${(i % 8) + 1}`,
      status: i % 7 === 0 ? 'Inactive' : 'Active', // occasional inactive member
    };
  });
};

const INITIAL_MEMBERS = generateMockMembers();

const StatusBadge: React.FC<{ status: MemberStatus }> = ({ status }) => {
  if (status === 'Active') {
    return <span className="inline-flex items-center rounded-md bg-emerald-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-emerald-600 border border-emerald-200">Active</span>;
  }
  return <span className="inline-flex items-center rounded-md bg-slate-50 px-2.5 py-1 text-[11px] font-bold tracking-wider text-slate-500 border border-slate-200">Inactive</span>;
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const day = String(date.getDate()).padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short' });
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
};

export const AdminMembers: React.FC = () => {
  const [members, setMembers] = useState<Member[]>(INITIAL_MEMBERS);
  const [search, setSearch] = useState('');
  const [filterRole, setFilterRole] = useState<MemberRole | 'All'>('All');
  
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 15;

  // Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create');
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formRole, setFormRole] = useState<MemberRole>('Employee');
  const [formDOJ, setFormDOJ] = useState('');
  const [formDOB, setFormDOB] = useState('');
  const [formStatus, setFormStatus] = useState<MemberStatus>('Active');

  const openCreateDrawer = () => {
    setDrawerMode('create');
    setEditingId(null);
    setFormName('');
    setFormEmail('');
    setFormRole('Employee');
    setFormDOJ('');
    setFormDOB('');
    setFormStatus('Active');
    setIsDrawerOpen(true);
  };

  const openEditDrawer = (member: Member) => {
    setDrawerMode('edit');
    setEditingId(member.id);
    setFormName(member.name);
    setFormEmail(member.email);
    setFormRole(member.role);
    setFormDOJ(member.dateOfJoining);
    setFormDOB(member.dateOfBirth);
    setFormStatus(member.status);
    setIsDrawerOpen(true);
  };

  const handleSaveMember = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName || !formEmail || !formDOJ || !formDOB) return;

    if (drawerMode === 'create') {
      const newMember: Member = {
        id: `m-${Date.now()}`,
        name: formName,
        email: formEmail,
        role: formRole,
        dateOfJoining: formDOJ,
        dateOfBirth: formDOB,
        status: formStatus,
      };
      setMembers([newMember, ...members]);
    } else if (drawerMode === 'edit' && editingId) {
      setMembers(members.map(m => m.id === editingId ? {
        ...m,
        name: formName,
        email: formEmail,
        role: formRole,
        dateOfJoining: formDOJ,
        dateOfBirth: formDOB,
        status: formStatus,
      } : m));
    }
    setIsDrawerOpen(false);
  };

  const filteredMembers = useMemo(() => {
    return members.filter(m => {
      const matchSearch = m.name.toLowerCase().includes(search.toLowerCase()) || 
                          m.email.toLowerCase().includes(search.toLowerCase());
      const matchRole = filterRole === 'All' || m.role === filterRole;
      return matchSearch && matchRole;
    });
  }, [members, search, filterRole]);

  const totalPages = Math.ceil(filteredMembers.length / PAGE_SIZE);
  const paginatedMembers = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredMembers.slice(start, start + PAGE_SIZE);
  }, [filteredMembers, page]);

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
              onChange={(e) => { setFilterRole(e.target.value as any); setPage(1); }}
              className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none focus:border-[#38bdf8] hover:bg-slate-50 shadow-sm"
            >
              <option value="All">All Roles</option>
              <option value="Admin">Admin</option>
              <option value="Leader">Leader</option>
              <option value="Employee">Employee</option>
            </select>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto pb-4">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Employee</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Role</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Date of Joining</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Date of Birth</th>
                  <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px] text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paginatedMembers.map(member => (
                  <tr key={member.id} className="transition hover:bg-slate-50/50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white shadow-sm ${GRADIENT_CYAN_PURPLE}`}>
                          {member.name.substring(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-slate-800 truncate">{member.name}</div>
                          <div className="text-xs text-slate-500 truncate mt-0.5">{member.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold ${
                        member.role === 'Admin' ? 'text-purple-600' :
                        member.role === 'Leader' ? 'text-blue-600' :
                        'text-slate-600'
                      }`}>
                        {member.role}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={member.status} />
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-600">{formatDate(member.dateOfJoining)}</td>
                    <td className="px-6 py-4 font-medium text-slate-600">{formatDate(member.dateOfBirth)}</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => openEditDrawer(member)}
                        className="rounded px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-[#14B8A6] border border-[#14B8A6]/30 transition hover:bg-[#14B8A6]/10"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
                {paginatedMembers.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                      No members found matching your search.
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
                Showing {((page - 1) * PAGE_SIZE) + 1} to {Math.min(page * PAGE_SIZE, filteredMembers.length)} of {filteredMembers.length} Members
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
                      onChange={e => setFormRole(e.target.value as MemberRole)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium bg-white"
                    >
                      <option value="Employee">Employee</option>
                      <option value="Leader">Leader</option>
                      <option value="Admin">Admin</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Status</label>
                    <select
                      required
                      value={formStatus}
                      onChange={e => setFormStatus(e.target.value as MemberStatus)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium bg-white"
                    >
                      <option value="Active">Active</option>
                      <option value="Inactive">Inactive</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Date of Joining</label>
                    <input
                      required
                      type="date"
                      value={formDOJ}
                      onChange={e => setFormDOJ(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium text-slate-700"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Date of Birth</label>
                    <input
                      required
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
