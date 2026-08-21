import React, { useState, useMemo } from 'react';
import { V2Shell } from '../dashboard/v2/V2Shell';

type TaskStatus = 'To Do' | 'In Progress' | 'Completed';

type TaskListing = {
  id: string;
  employeeName: string;
  projectName: string;
  taskName: string;
  usedHours: number;
  status: TaskStatus;
  date: string;
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

const applyDatePreset = (preset: string) => {
  const today = new Date();
  let start = new Date(today);
  let end = new Date(today);

  switch (preset) {
    case 'Today':
      break;
    case 'Yesterday':
      start.setDate(today.getDate() - 1);
      end = new Date(start);
      break;
    case 'Last 7 days':
      start.setDate(today.getDate() - 6);
      break;
    case 'Last week':
      start.setDate(today.getDate() - 13);
      end.setDate(today.getDate() - 7);
      break;
    case 'Last 2 weeks':
      start.setDate(today.getDate() - 13);
      break;
    case 'This month':
      start = new Date(today.getFullYear(), today.getMonth(), 1);
      end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      break;
    case 'Last month':
      start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      end = new Date(today.getFullYear(), today.getMonth(), 0);
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

const MOCK_TASKS: TaskListing[] = Array.from({ length: 45 }).map((_, i) => {
  const employees = ['David Evans', 'Eve Foster', 'Frank Green', 'Grace Hall', 'Henry Ives', 'Ivy Jones', 'Jack King', 'Karen Lee'];
  const projects = ['Website Redesign', 'Mobile App V2', 'Database Migration', 'Marketing Campaign', 'Client Portal', 'API Integration'];
  const tasks = ['Design UI Mockups', 'Develop Backend APIs', 'Write Unit Tests', 'Setup CI/CD', 'Client Meeting', 'Code Review', 'Bug Fixing'];
  const statuses: TaskStatus[] = ['To Do', 'In Progress', 'Completed'];

  const d = new Date();
  d.setDate(d.getDate() - (i % 30)); // distribute tasks over the last 30 days
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');

  return {
    id: `t-${i}`,
    employeeName: employees[i % employees.length],
    projectName: projects[i % projects.length],
    taskName: tasks[i % tasks.length],
    usedHours: Math.floor(Math.random() * 40) + 1,
    status: statuses[i % statuses.length],
    date: `${y}-${m}-${day}`,
  };
});

const StatusBadge: React.FC<{ status: TaskStatus }> = ({ status }) => {
  switch (status) {
    case 'To Do':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#64748B] border border-[#CBD5E1]">To Do</span>;
    case 'In Progress':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#3B82F6] border border-[#3B82F6]">In Progress</span>;
    case 'Completed':
      return <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1 text-[11px] font-bold tracking-wider text-[#10B981] border border-[#10B981]">Completed</span>;
    default:
      return null;
  }
};

const EmployeeAccordionCard: React.FC<{ group: { name: string; tasks: TaskListing[] } }> = ({ group }) => {
  const [isOpen, setIsOpen] = useState(false);
  const totalHours = group.tasks.reduce((sum, t) => sum + t.usedHours, 0);
  const completedCount = group.tasks.filter(t => t.status === 'Completed').length;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between border-b border-slate-100 bg-slate-50/50 p-5 text-left transition hover:bg-slate-100/50 outline-none"
      >
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-[#0ea5e9] to-[#8b5cf6] text-sm font-bold text-white shadow-sm">
            {group.name.substring(0, 2).toUpperCase()}
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-800">{group.name}</h3>
            <p className="text-xs font-medium text-slate-500 mt-0.5">
              {group.tasks.length} Assigned Task{group.tasks.length !== 1 ? 's' : ''} &bull; {completedCount} Completed
            </p>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex flex-col items-end">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Logged</span>
            <span className="text-lg font-extrabold text-[#14B8A6]">{totalHours} hrs</span>
          </div>
          <div className={`flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </button>

      <div className={`transition-all duration-300 ease-in-out ${isOpen ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'}`}>
        <div className="divide-y divide-slate-50 p-3">
          {group.tasks.map(task => (
            <div key={task.id} className="group flex items-center justify-between rounded-xl p-3 transition hover:bg-slate-50">
              <div className="flex flex-1 items-start gap-4">
                <div className="mt-1">
                  {task.status === 'Completed' ? (
                    <svg className="h-5 w-5 text-[#10B981]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                  ) : task.status === 'In Progress' ? (
                    <svg className="h-5 w-5 text-[#3B82F6]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-slate-300 mt-0.5"></div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-sm font-bold text-slate-800">{task.taskName}</h4>
                  <div className="mt-1 flex items-center gap-2 text-xs font-medium text-slate-500">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-600">{task.projectName}</span>
                    <span>&bull;</span>
                    <span className="text-[#14B8A6]">{task.usedHours} hrs spent</span>
                    <span>&bull;</span>
                    <span>{formatDate(task.date)}</span>
                  </div>
                </div>
              </div>
              
              <div className="ml-4 shrink-0">
                <StatusBadge status={task.status} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const AdminTaskListing: React.FC = () => {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<TaskStatus | 'All'>('All');
  
  // Date filter state
  const [dateFilterOpen, setDateFilterOpen] = useState(false);
  const [datePreset, setDatePreset] = useState<string>('All Time');
  const [filterStartDate, setFilterStartDate] = useState('');
  const [filterEndDate, setFilterEndDate] = useState('');

  const [page, setPage] = useState(1);
  const PAGE_SIZE = 5;

  const filteredTasks = useMemo(() => {
    return MOCK_TASKS.filter(t => {
      const matchSearch = t.employeeName.toLowerCase().includes(search.toLowerCase()) || 
                          t.projectName.toLowerCase().includes(search.toLowerCase()) || 
                          t.taskName.toLowerCase().includes(search.toLowerCase());
      const matchStatus = filterStatus === 'All' || t.status === filterStatus;
      
      let matchDate = true;
      if (filterStartDate || filterEndDate) {
        if (filterStartDate && t.date < filterStartDate) matchDate = false;
        if (filterEndDate && t.date > filterEndDate) matchDate = false;
      }
      
      return matchSearch && matchStatus && matchDate;
    });
  }, [search, filterStatus, filterStartDate, filterEndDate]);

  const groupedTasks = useMemo(() => {
    const groups: Record<string, TaskListing[]> = {};
    filteredTasks.forEach(t => {
      if (!groups[t.employeeName]) groups[t.employeeName] = [];
      groups[t.employeeName].push(t);
    });
    return Object.entries(groups)
      .map(([name, tasks]) => ({ name, tasks }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [filteredTasks]);

  const totalPages = Math.ceil(groupedTasks.length / PAGE_SIZE);
  const paginatedGroups = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return groupedTasks.slice(start, start + PAGE_SIZE);
  }, [groupedTasks, page]);

  return (
    <V2Shell
      title="V2 Task Listing"
      subtitle="View all tasks grouped by employee and track their hours."
    >
      <div className="mx-auto max-w-5xl space-y-8 pb-20">
        
        {/* Filter Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-1 items-center gap-2 px-2">
            <svg className="h-5 w-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search by employee, project, or task..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 text-slate-700"
            />
          </div>
          
          <div className="h-8 w-px bg-slate-200 hidden lg:block"></div>

          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3 border-r border-slate-200 pr-4">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">STATUS:</span>
              <select
                value={filterStatus}
                onChange={(e) => { setFilterStatus(e.target.value as any); setPage(1); }}
                className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none focus:border-[#38bdf8] hover:bg-slate-50 shadow-sm"
              >
                <option value="All">All Statuses</option>
                <option value="To Do">To Do</option>
                <option value="In Progress">In Progress</option>
                <option value="Completed">Completed</option>
              </select>
            </div>

            {/* Date Filter */}
            <div className="relative">
              <button
                onClick={() => setDateFilterOpen(!dateFilterOpen)}
                className="flex items-center gap-2 rounded-lg border border-[#38bdf8] bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 shadow-sm"
              >
                <span className="text-[#0ea5e9]">
                  {datePreset !== 'All Time' ? datePreset : (filterStartDate ? `${filterStartDate} to ${filterEndDate || 'Any'}` : 'Filter Date')}
                </span>
                <svg className="h-4 w-4 text-[#0ea5e9]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>
              
              {dateFilterOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setDateFilterOpen(false)} />
                  <div className="absolute right-0 z-20 mt-2 flex w-[480px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl animate-in fade-in slide-in-from-top-2">
                    <div className="w-1/3 border-r border-slate-100 bg-slate-50 p-2 space-y-1">
                      {['All Time', 'Today', 'Yesterday', 'Last 7 days', 'Last week', 'Last 2 weeks', 'This month', 'Last month'].map(preset => (
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

        {/* Employee Cards list */}
        <div className="space-y-6">
          {paginatedGroups.map((group) => (
            <EmployeeAccordionCard key={group.name} group={group} />
          ))}
          
          {paginatedGroups.length === 0 && (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 border-dashed bg-white py-20">
              <svg className="mb-3 h-10 w-10 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
              </svg>
              <h3 className="text-sm font-bold text-slate-700">No tasks found</h3>
              <p className="mt-1 text-xs text-slate-500">Try adjusting your search or filters.</p>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-6 py-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500">
              Showing {((page - 1) * PAGE_SIZE) + 1} to {Math.min(page * PAGE_SIZE, groupedTasks.length)} of {groupedTasks.length} Employees
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition disabled:opacity-40 hover:bg-slate-50"
              >
                Prev
              </button>
              <span className="px-3 text-xs font-bold text-slate-800">{page} / {totalPages}</span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition disabled:opacity-40 hover:bg-slate-50"
              >
                Next
              </button>
            </div>
          </div>
        )}

      </div>
    </V2Shell>
  );
};
