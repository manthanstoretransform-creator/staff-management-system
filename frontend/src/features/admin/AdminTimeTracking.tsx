import React, { useState, useMemo } from 'react';
import { members } from '../dashboard/v2/mockData';
import { V2Shell } from '../dashboard/v2/V2Shell';
import { useGetTimeTrackingDetailsQuery, useGetTimeTrackingQuery } from '../../store/api/timeTrackingApi';
import { InlineRefreshIndicator } from '../../components/InlineRefreshIndicator';

// Generate some dummy time entries based on members
const TODAY = new Date();
const formatDateString = (d: Date) => d.toISOString().split('T')[0];
const todayStr = formatDateString(TODAY);

export interface TimeEntry {
  id: string;
  employeeId: string;
  date: string; // YYYY-MM-DD
  clockIn: string;
  lunchStart: string;
  lunchEnd: string;
  clockOut: string;
  employeeName?: string;
  totalHours?: string;
}

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
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0]
  };
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const formatter = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
  return formatter.format(date); // e.g. "12 Jun 2026"
};

const formatDateTime = (dateStr: string | null) => dateStr
  ? new Date(dateStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  : '-';

const calculateTotalHours = (clockIn: string, lunchStart: string, lunchEnd: string, clockOut: string) => {
  const parseTime = (timeStr: string) => {
    if (!timeStr || timeStr === '-') return 0;
    const match = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/i);
    if (!match) return 0;
    let [_, hStr, mStr, p] = match;
    let hours = parseInt(hStr);
    if (p.toUpperCase() === 'PM' && hours < 12) hours += 12;
    if (p.toUpperCase() === 'AM' && hours === 12) hours = 0;
    return hours * 60 + parseInt(mStr);
  };
  
  const inMins = parseTime(clockIn);
  const outMins = parseTime(clockOut);
  const lsMins = parseTime(lunchStart);
  const leMins = parseTime(lunchEnd);
  
  if (inMins === 0 || outMins === 0) return '-';
  
  let totalMins = (outMins - inMins);
  if (lsMins > 0 && leMins > 0 && leMins > lsMins) {
    totalMins -= (leMins - lsMins);
  }
  
  if (totalMins <= 0) return '-';
  
  const h = Math.floor(totalMins / 60);
  const m = totalMins % 60;
  return `${h}h ${m}m`;
};

const PAGE_SIZE = 50;
const GRADIENT_CYAN_PURPLE = "bg-gradient-to-r from-[#0ea5e9] to-[#8b5cf6]";

export const AdminTimeTracking: React.FC = () => {
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [search, setSearch] = useState('');
  
  // By default show today date
  const todayRange = applyDatePreset('Today');
  const [datePreset, setDatePreset] = useState('Today');
  const [filterStartDate, setFilterStartDate] = useState(todayRange.start);
  const [filterEndDate, setFilterEndDate] = useState(todayRange.end);
  const [dateFilterOpen, setDateFilterOpen] = useState(false);

  const [page, setPage] = useState(1);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null);

  const { data: trackingData, isLoading, isFetching, isError } = useGetTimeTrackingQuery({
    start_date: filterStartDate || undefined,
    end_date: filterEndDate || undefined,
    page,
    limit: PAGE_SIZE,
  });
  const { data: employeeDetails, isLoading: isLoadingDetails } = useGetTimeTrackingDetailsQuery({
    employeeId: selectedEmployeeId || 0,
    start_date: filterStartDate || undefined,
    end_date: filterEndDate || undefined,
  }, { skip: selectedEmployeeId === null });

  // Keep the previous range's rows visible while the new one loads instead of
  // covering the table every time a date filter changes.
  const showFirstLoad = isLoading && !trackingData;

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [formEmployeeId, setFormEmployeeId] = useState('');
  const [formDate, setFormDate] = useState(todayStr);
  const [formClockIn, setFormClockIn] = useState('09:00 AM');
  const [formLunchStart, setFormLunchStart] = useState('01:00 PM');
  const [formLunchEnd, setFormLunchEnd] = useState('02:00 PM');
  const [formClockOut, setFormClockOut] = useState('06:00 PM');

  const getEmployeeName = (id: string, name?: string) => name || members.find(m => m.id === id)?.name || id;

  const apiEntries = useMemo(() => (trackingData?.items || []).map((entry) => ({
    id: `${entry.employee_id}-${entry.date}-${entry.start_time || 'entry'}`,
    employeeId: String(entry.employee_id),
    employeeName: entry.name,
    date: entry.date,
    clockIn: entry.start_time ? new Date(entry.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-',
    lunchStart: '-',
    lunchEnd: '-',
    clockOut: entry.end_time ? new Date(entry.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
    totalHours: entry.total_hours,
  })), [trackingData?.items]);

  const filteredEntries = useMemo(() => {
    return [...apiEntries, ...entries].filter(e => {
      if (search && !getEmployeeName(e.employeeId, e.employeeName).toLowerCase().includes(search.toLowerCase())) return false;
      
      if (filterStartDate && e.date < filterStartDate) return false;
      if (filterEndDate && e.date > filterEndDate) return false;
      
      return true;
    }).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [apiEntries, entries, search, filterStartDate, filterEndDate]);

  const totalPages = trackingData?.pagination?.total_pages || Math.ceil(filteredEntries.length / PAGE_SIZE) || 1;
  const paginatedEntries = trackingData ? filteredEntries : filteredEntries.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formEmployeeId) return;

    const newEntry: TimeEntry = {
      id: `t-${Date.now()}`,
      employeeId: formEmployeeId,
      date: formDate,
      clockIn: formClockIn,
      lunchStart: formLunchStart,
      lunchEnd: formLunchEnd,
      clockOut: formClockOut
    };

    setEntries(prev => [newEntry, ...prev]);
    setIsDrawerOpen(false);
  };

  const closeDrawer = () => setIsDrawerOpen(false);
  const openDrawer = () => {
    setFormEmployeeId(members[0]?.id || '');
    setFormDate(todayStr);
    setFormClockIn('09:00 AM');
    setFormLunchStart('01:00 PM');
    setFormLunchEnd('02:00 PM');
    setFormClockOut('06:00 PM');
    setIsDrawerOpen(true);
  };

  return (
    <V2Shell title="Time Tracking" subtitle="Monitor and manage employee time logs">
      <div className="mx-auto max-w-7xl space-y-6 pb-20">
      
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-1 items-center gap-2 px-2">
          <svg className="h-5 w-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search by employee name..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 text-slate-700"
          />
        </div>

        <div className="h-8 w-px bg-slate-200 hidden lg:block"></div>

        <div className="flex flex-wrap items-center gap-4">
          {/* Date Range Filter */}
          <div className="relative">
            <button
              onClick={() => setDateFilterOpen(!dateFilterOpen)}
              className="flex items-center gap-2 rounded-lg border border-[#38bdf8] bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 shadow-sm"
            >
              <span className="text-[#0ea5e9]">
                {datePreset !== 'All Time' ? datePreset : (filterStartDate ? `${formatDate(filterStartDate)} to ${formatDate(filterEndDate) || 'Any'}` : 'Filter Date')}
              </span>
              <svg className="h-4 w-4 text-[#0ea5e9]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </button>
            
            {dateFilterOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setDateFilterOpen(false)} />
                <div className="absolute right-0 sm:right-auto lg:right-0 z-20 mt-2 flex flex-col sm:flex-row w-[calc(100vw-2rem)] sm:w-[480px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl animate-in fade-in slide-in-from-top-2 max-w-sm sm:max-w-none">
                  <div className="w-full sm:w-1/3 border-b sm:border-b-0 sm:border-r border-slate-100 bg-slate-50 p-2 space-y-1 overflow-x-auto sm:overflow-visible flex sm:block gap-2">
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
                        className={`shrink-0 w-auto sm:w-full rounded-md px-3 py-2 text-left text-xs font-semibold transition ${datePreset === preset ? 'bg-white border border-slate-200 text-[#0ea5e9] shadow-sm' : 'text-slate-600 hover:bg-slate-200/50'}`}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                  <div className="w-full sm:w-2/3 p-4 flex flex-col bg-white">
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
                            className="w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8]"
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
                            className="w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8]"
                          />
                        </div>
                      </div>
                      <div className="mt-6 flex justify-end gap-2">
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

          <button
            onClick={openDrawer}
            className={`rounded-lg px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
          >
            + Add Manually Time
          </button>
        </div>
      </div>

      <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {showFirstLoad ? (
          <div className="absolute inset-0 z-10 flex items-start justify-center bg-white/55 pt-20 backdrop-blur-[2px]">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" role="status" aria-label="Loading time tracking" />
          </div>
        ) : (
          <div className="pointer-events-none absolute right-3 top-3 z-10">
            <InlineRefreshIndicator active={isFetching} />
          </div>
        )}
        <div className="overflow-x-auto pb-4">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Employee</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Date</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Start Time (Clock In)</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Clock Out</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider text-[11px]">Total Hours</th>
                <th className="px-6 py-4 text-right font-bold uppercase tracking-wider text-[11px]">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isError ? (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-rose-500">Unable to load time tracking data.</td></tr>
              ) : paginatedEntries.map(entry => (
                <tr key={entry.id} className="transition hover:bg-slate-50/80">
                  <td className="px-6 py-4">
                    <div className="font-semibold text-slate-800">{getEmployeeName(entry.employeeId, entry.employeeName)}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-600">{formatDate(entry.date)}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">
                      {entry.clockIn}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {entry.clockOut ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                        {entry.clockOut}
                      </span>
                    ) : (
                      <span className="text-xs font-bold italic text-slate-400">Working...</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-bold text-slate-700">
                      {entry.totalHours || calculateTotalHours(entry.clockIn, entry.lunchStart, entry.lunchEnd, entry.clockOut)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button type="button" onClick={() => setSelectedEmployeeId(Number(entry.employeeId))} className="rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-600 transition hover:bg-indigo-100">View</button>
                  </td>
                </tr>
              ))}
              
              {paginatedEntries.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-20 text-center">
                    <div className="flex flex-col items-center justify-center">
                      <svg className="mb-4 h-12 w-12 text-slate-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <h3 className="text-sm font-bold text-slate-700">No time entries found</h3>
                      <p className="mt-1 text-xs text-slate-500">No records exist for the selected date range and employee.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-6 py-4 shadow-sm">
          <span className="text-xs font-medium text-slate-500">
            Showing {((page - 1) * PAGE_SIZE) + 1} to {Math.min(page * PAGE_SIZE, trackingData?.pagination?.total || filteredEntries.length)} of {trackingData?.pagination?.total || filteredEntries.length} Entries
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
            <div className="flex h-8 items-center justify-center px-3 text-sm font-semibold text-slate-700">
              {page} / {totalPages}
            </div>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
            </button>
          </div>
        </div>
      )}

      {selectedEmployeeId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl" role="dialog" aria-modal="true" aria-label="Employee time details">
            <div className="flex items-start justify-between border-b border-slate-100 bg-slate-50 px-6 py-5">
              <div>
                <h2 className="text-xl font-black text-slate-800">Time Tracking Details</h2>
                <p className="mt-1 text-sm font-semibold text-slate-500">Employee summary for the selected date range</p>
              </div>
              <button type="button" onClick={() => setSelectedEmployeeId(null)} className="rounded-lg p-2 text-slate-400 transition hover:bg-white hover:text-slate-700" aria-label="Close time details">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="max-h-[calc(90vh-86px)] overflow-y-auto p-6">
              {isLoadingDetails && !employeeDetails ? <div className="flex justify-center py-16"><div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" /></div> : employeeDetails ? (
                <>
                  <div className="flex items-center gap-4 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-r from-[#0ea5e9] to-[#8b5cf6] text-sm font-black text-white">{employeeDetails.employee.name.slice(0, 2).toUpperCase()}</div>
                    <div><h3 className="font-black text-slate-800">{employeeDetails.employee.name}</h3><p className="text-sm text-slate-500">{employeeDetails.employee.designation || employeeDetails.employee.email}</p></div>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
                    {[['Start date', formatDate(employeeDetails.start_date)], ['End date', formatDate(employeeDetails.end_date)], ['Start time', formatDateTime(employeeDetails.summary.start_time)], ['End time', formatDateTime(employeeDetails.summary.end_time)], ['Total hours', employeeDetails.summary.total_hours]].map(([label, value]) => <div key={label} className="min-h-[86px] rounded-xl border border-slate-100 bg-slate-50 p-4"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div><div className="mt-2 text-sm font-bold leading-5 text-slate-800">{value}</div></div>)}
                  </div>
                  <h3 className="mt-6 text-xs font-black uppercase tracking-widest text-blue-500">Projects</h3>
                  {employeeDetails.projects.length ? <div className="mt-3 space-y-3">{employeeDetails.projects.map((project) => <div key={project.id} className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-bold text-slate-800">{project.name}</h4><span className="rounded-full px-2.5 py-1 text-[11px] font-bold" style={{ color: project.status.color, backgroundColor: `${project.status.color}18` }}>{project.status.name}</span></div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total hours</div><div className="mt-1 text-xs font-semibold text-slate-700">{project.total_hours}</div></div>
                      <div className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total seconds</div><div className="mt-1 text-xs font-semibold text-slate-700">{project.total_seconds}</div></div>
                    </div>
                    <div className="mt-4 overflow-hidden rounded-lg border border-slate-100"><div className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Tasks</div>{project.tasks.length ? project.tasks.map((task) => <div key={task.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-3 py-3 last:border-b-0"><div className="min-w-0"><div className="truncate text-xs font-bold text-slate-800">{task.name}</div><div className="mt-1 text-[11px] font-semibold text-slate-500">{task.total_hours} ({task.total_seconds} seconds)</div></div><span className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold" style={{ color: task.status.color, backgroundColor: `${task.status.color}18` }}>{task.status.name}</span></div>) : <p className="px-3 py-4 text-xs text-slate-500">No tasks recorded.</p>}</div>
                  </div>)}</div> : <p className="mt-3 rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">No projects recorded.</p>}
                </>
              ) : <p className="py-16 text-center text-sm text-slate-500">No details found.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Slide-over Drawer for Adding Time */}
      <div className={`fixed inset-0 z-50 overflow-hidden ${isDrawerOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}>
        <div className={`absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-300 ${isDrawerOpen ? 'opacity-100' : 'opacity-0'}`} onClick={closeDrawer} />
        <div className={`absolute inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isDrawerOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
              <h3 className="text-lg font-bold text-slate-800">Add Manually Time</h3>
              <button type="button" onClick={closeDrawer} className="text-slate-400 hover:text-slate-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <form id="time-form" onSubmit={handleSave} className="p-6 space-y-6">
                
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Employee Name</label>
                  <select
                    required
                    value={formEmployeeId}
                    onChange={e => setFormEmployeeId(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                  >
                    {members.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Date</label>
                  <input
                    required
                    type="date"
                    value={formDate}
                    onChange={e => setFormDate(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Start Time (Clock In)</label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. 09:00 AM"
                      value={formClockIn}
                      onChange={e => setFormClockIn(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Clock Out</label>
                    <input
                      type="text"
                      placeholder="e.g. 06:00 PM"
                      value={formClockOut}
                      onChange={e => setFormClockOut(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">Lunch Time (Start)</label>
                    <input
                      type="text"
                      placeholder="e.g. 01:00 PM"
                      value={formLunchStart}
                      onChange={e => setFormLunchStart(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">End Lunch Time</label>
                    <input
                      type="text"
                      placeholder="e.g. 02:00 PM"
                      value={formLunchEnd}
                      onChange={e => setFormLunchEnd(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] text-sm font-medium"
                    />
                  </div>
                </div>

              </form>
            </div>
            
            <div className="border-t border-slate-100 p-6 bg-slate-50">
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={closeDrawer}
                  className="flex-1 rounded-lg border border-slate-200 bg-white py-2.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  form="time-form"
                  className={`flex-1 rounded-lg py-2.5 text-sm font-bold text-white shadow-md transition hover:opacity-90 ${GRADIENT_CYAN_PURPLE}`}
                >
                  Save Entry
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      </div>
    </V2Shell>
  );
};
