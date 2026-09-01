import React, { useState, useEffect } from "react";
import { V2Shell } from "../dashboard/v2/V2Shell";
import { useGetProjectTaskSummaryQuery } from "../../store/api/reportsApi";
import { 
  useGetAllProjectsQuery,
  useGetProjectMetadataQuery,
  useGetAssignableEmployeesQuery,
  useCreateTaskMutation
} from "../../store/api/projectsApi";
import { useFeedback } from "../../components/FeedbackProvider";
import { InlineRefreshIndicator } from "../../components/InlineRefreshIndicator";
import { formatHMS } from "../../utils/duration";

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  const day = date.getDate().toString().padStart(2, "0");
  const month = date.toLocaleString("en-US", { month: "short" });
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
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0]
  };
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
        <select value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setPage(1); }} className="rounded-md border border-slate-300 py-1.5 pl-3 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
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


export const AdminTaskListing: React.FC = () => {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  
  const [datePreset, setDatePreset] = useState('All Time');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [dateFilterOpen, setDateFilterOpen] = useState(false);
  
  const [filterProjectId, setFilterProjectId] = useState<number | null>(null);

  const [expandedProjects, setExpandedProjects] = useState<Record<number, boolean>>({});

  const { data: allProjects } = useGetAllProjectsQuery();
  const { data: metadata } = useGetProjectMetadataQuery();
  const { data: employeesData } = useGetAssignableEmployeesQuery();
  const [createTask] = useCreateTaskMutation();
  const { showToast } = useFeedback();

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [formProjectId, setFormProjectId] = useState<number | "">("");
  const [formTaskName, setFormTaskName] = useState("");
  const [formAssigneeId, setFormAssigneeId] = useState<number | "">("");
  const [formStatusId, setFormStatusId] = useState<number>(1);
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading, isFetching, refetch } = useGetProjectTaskSummaryQuery({
    page,
    limit,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    project_id: filterProjectId ? [filterProjectId] : undefined,
  });

  const showFirstLoad = isLoading && !data;
  const projects = data?.projects || [];
  const pagination = data?.pagination;

  // Initialize expanded state for newly loaded projects
  useEffect(() => {
    if (projects.length > 0) {
      setExpandedProjects((prev) => {
        const next = { ...prev };
        let changed = false;
        projects.forEach((p) => {
          if (next[p.id] === undefined) {
            next[p.id] = true;
            changed = true;
          }
        });
        return changed ? next : prev;
      });
    }
  }, [projects]);

  const toggleProject = (id: number) => {
    setExpandedProjects((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const collapseAll = () => {
    const next: Record<number, boolean> = {};
    projects.forEach((p) => {
      next[p.id] = false;
    });
    setExpandedProjects(next);
  };
  
  const expandAll = () => {
    const next: Record<number, boolean> = {};
    projects.forEach((p) => {
      next[p.id] = true;
    });
    setExpandedProjects(next);
  };
  
  const isAnyExpanded = Object.values(expandedProjects).some((v) => v);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formProjectId || !formTaskName) return;

    try {
      await createTask({
        projectId: Number(formProjectId),
        body: {
          name: formTaskName,
          assignee_id: formAssigneeId === "" ? null : Number(formAssigneeId),
          status_id: formStatusId,
        },
      }).unwrap();
      setIsDrawerOpen(false);
      setFormTaskName("");
      setFormError(null);
      showToast("Task created successfully.", "success");
      refetch();
    } catch (err: any) {
      console.error(err);
      const errorMsg = err?.data?.detail || err?.data?.message || "Unable to create task. Please try again.";
      setFormError(errorMsg);
      showToast(errorMsg, "error");
    }
  };

  return (
    <V2Shell 
      title="Project Tasks" 
      subtitle="Review tasks grouped by project"
      actions={
        <button
          onClick={() => {
            setFormProjectId("");
            setFormTaskName("");
      setFormError(null);
            setFormAssigneeId("");
            setFormStatusId(metadata?.task_statuses?.[0]?.id || 1);
            setFormError(null);
            setIsDrawerOpen(true);
          }}
          className="rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90"
        >
          + Add Task
        </button>
      }
    >
      <div className="w-full px-4 py-8 sm:px-6 lg:px-8">
        {/* Toolbar */}
        <div className="mb-6 flex flex-wrap items-center justify-end gap-3">
            {/* Project Filter */}
            <select
              value={filterProjectId || ''}
              onChange={(e) => {
                setFilterProjectId(e.target.value ? Number(e.target.value) : null);
                setPage(1);
              }}
              className="max-w-[220px] rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
            >
              <option value="">All Projects</option>
              {allProjects?.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.project_name}
                </option>
              ))}
            </select>
            
            {/* Date Filter */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setDateFilterOpen(!dateFilterOpen)}
                className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold text-[#0ea5e9] transition hover:bg-slate-50 hover:text-[#0ea5e9]"
              >
                <span>
                  {datePreset === 'All Time'
                    ? 'All Time'
                    : datePreset === 'Custom'
                      ? `${formatDate(startDate)} - ${formatDate(endDate)}`
                      : datePreset}
                </span>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>
              
              {dateFilterOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setDateFilterOpen(false)} />
                  <div className="absolute right-0 z-20 mt-2 flex flex-col sm:flex-row w-[calc(100vw-2rem)] sm:w-[480px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl animate-in fade-in slide-in-from-top-2 max-w-sm sm:max-w-none">
                    <div className="w-full sm:w-1/3 border-b sm:border-b-0 sm:border-r border-slate-100 bg-slate-50 p-2 space-y-1 overflow-x-auto sm:overflow-visible flex sm:block gap-2">
                      {['All Time', 'Today', 'Yesterday', 'Last 7 days', 'Last week', 'Last 2 weeks', 'This month', 'Last month'].map(preset => (
                        <button
                          key={preset}
                          onClick={() => {
                            setDatePreset(preset);
                            if (preset === 'All Time') {
                              setStartDate('');
                              setEndDate('');
                            } else {
                              const { start, end } = applyDatePreset(preset);
                              setStartDate(start);
                              setEndDate(end);
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
                            value={startDate}
                            onChange={(e) => {
                              setStartDate(e.target.value);
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
                            value={endDate}
                            onChange={(e) => {
                              setEndDate(e.target.value);
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
                            setStartDate('');
                            setEndDate('');
                            setDatePreset('All Time');
                            setPage(1);
                            setDateFilterOpen(false);
                          }} 
                          className="rounded-md px-4 py-2 text-xs font-bold text-slate-500 hover:bg-slate-100 transition"
                        >
                          Clear
                        </button>
                        <button onClick={() => setDateFilterOpen(false)} className="rounded-md bg-[#38bdf8] px-4 py-2 text-xs font-bold text-white hover:bg-[#0284c7] transition shadow-sm">
                          Apply
                        </button>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
            
            <button
              type="button"
              onClick={isAnyExpanded ? collapseAll : expandAll}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-bold text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
            >
              {isAnyExpanded ? "Collapse All" : "Expand All"}
            </button>
        </div>

        {/* Grouped Projects */}
        {showFirstLoad ? (
          <div className="flex justify-center p-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
          </div>
        ) : (
          <div className="relative space-y-6">
            <div className="pointer-events-none absolute right-0 -top-9 z-10">
              <InlineRefreshIndicator active={isFetching && !showFirstLoad} />
            </div>

            {projects.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
                <svg
                  className="mx-auto h-12 w-12 text-slate-300"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>
                <h3 className="mt-4 text-sm font-bold text-slate-800">
                  No projects found
                </h3>
                <p className="mt-1 text-xs font-medium text-slate-500">
                  Try adjusting your filters or date range.
                </p>
              </div>
            ) : (
              projects.map((project) => {
                const isExpanded = expandedProjects[project.id] !== false;
                return (
                  <div
                    key={project.id}
                    className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden transition-all"
                  >
                    {/* Header */}
                    <div
                      onClick={() => toggleProject(project.id)}
                      className="flex cursor-pointer items-center justify-between bg-slate-50 p-6 transition hover:bg-slate-100"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] text-sm font-bold text-white shadow-sm">
                          {project.project_name ? project.project_name.charAt(0).toUpperCase() : 'P'}
                        </div>
                        <div>
                          <h3 className="text-lg font-black text-slate-800">
                            {project.project_name}
                          </h3>
                          <div className="flex items-center gap-2 mt-0.5">
                            <p className="text-xs font-semibold text-slate-500">
                              {project.total_task_count} Task{project.total_task_count !== 1 ? 's' : ''} &bull;{" "}
                              {formatHMS(project.total_task_seconds)} Total Time
                            </p>
                            {project.status && (
                              <span
                                className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider text-white"
                                style={{ backgroundColor: project.status.color }}
                              >
                                {project.status.name}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <span className="text-xs font-bold text-slate-400">Created {formatDate(project.created_date)}</span>
                        <svg
                          className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </div>
                    </div>

                    {/* Tasks List */}
                    {isExpanded && (
                      <div className="divide-y divide-slate-100">
                        {project.tasks.length === 0 ? (
                          <div className="p-6 text-center text-sm font-semibold text-slate-500">
                            No tasks found for this project.
                          </div>
                        ) : (
                          project.tasks.map((task) => (
                            <div
                              key={task.id}
                              className="flex items-center justify-between p-6 transition hover:bg-slate-50/50"
                            >
                              <div className="flex items-start gap-4">
                                <svg
                                  className="mt-0.5 h-5 w-5 text-slate-400"
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth="2"
                                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                  />
                                </svg>
                                <div>
                                  <h4 className="text-sm font-bold text-slate-700 line-clamp-2">
                                    {task.task_name}
                                  </h4>
                                  <div className="mt-1 flex items-center gap-3 text-[11px] font-semibold text-slate-400">
                                    <span className="flex items-center gap-1">
                                      Created {formatDate(task.task_created_date)}
                                    </span>
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-4 text-right">
                                <div className="text-sm font-bold text-slate-800">
                                  {formatHMS(task.total_tracked_seconds)}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}

            {/* Pagination */}
            {pagination && pagination.total_pages > 1 && (
              <Pagination page={page} totalPages={pagination.total_pages} totalItems={pagination.total_projects} limit={limit} setPage={setPage} setLimit={setLimit} />
            )}
          </div>
        )}
      </div>
        {/* Create Task Drawer */}
        <div className={`fixed inset-0 z-50 overflow-hidden ${isDrawerOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
          <div
            className={`absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-300 ${isDrawerOpen ? "opacity-100" : "opacity-0"}`}
            onClick={() => setIsDrawerOpen(false)}
          />
          <div
            className={`absolute inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl transition-transform duration-300 ease-in-out ${isDrawerOpen ? "translate-x-0" : "translate-x-full"}`}
          >
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
                <div>
                  <h2 className="text-xl font-black text-slate-800">
                    Create Task
                  </h2>
                  <p className="mt-1 text-sm font-semibold text-slate-500">
                    Assign a new task to a project
                  </p>
                </div>
                <button
                  onClick={() => setIsDrawerOpen(false)}
                  className="rounded-full p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-600"
                >
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
  
              <div className="flex-1 overflow-y-auto p-6">
                
                {formError && (
                  <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 text-rose-600">
                    <svg className="mt-0.5 h-5 w-5 shrink-0 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm font-semibold">{formError}</p>
                  </div>
                )}
                <form id="task-form" onSubmit={handleCreateTask} className="space-y-6">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                      Project <span className="text-rose-500">*</span>
                    </label>
                    <select
                      required
                      value={formProjectId}
                      onChange={(e) => setFormProjectId(e.target.value === "" ? "" : Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
                    >
                      <option value="" disabled>Select Project</option>
                      {allProjects?.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.project_name}
                        </option>
                      ))}
                    </select>
                  </div>
  
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                      Task Name <span className="text-rose-500">*</span>
                    </label>
                    <input
                      required
                      type="text"
                      value={formTaskName}
                      onChange={(e) => setFormTaskName(e.target.value)}
                      placeholder="e.g. Design Homepage"
                      className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
                    />
                  </div>
  
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                      Assign To
                    </label>
                    <select
                      value={formAssigneeId}
                      onChange={(e) => setFormAssigneeId(e.target.value === "" ? "" : Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
                    >
                      <option value="">Unassigned</option>
                      {employeesData?.map((emp) => (
                        <option key={emp.id} value={emp.id}>
                          {emp.name}
                        </option>
                      ))}
                    </select>
                  </div>
  
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                      Status
                    </label>
                    <select
                      value={formStatusId}
                      onChange={(e) => setFormStatusId(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
                    >
                      {metadata?.task_statuses?.map((st: any) => (
                        <option key={st.id} value={st.id}>
                          {st.task_status}
                        </option>
                      ))}
                    </select>
                  </div>
                </form>
              </div>
  
              <div className="border-t border-slate-100 bg-slate-50 p-6 flex gap-3">
                <button
                  type="button"
                  onClick={() => setIsDrawerOpen(false)}
                  className="flex-1 rounded-lg border border-slate-200 bg-white py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  form="task-form"
                  className="flex-1 rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] py-3 text-sm font-bold text-white transition hover:opacity-90 shadow-md"
                >
                  Create Task
                </button>
              </div>
            </div>
          </div>
        </div>
      </V2Shell>
  );
};
