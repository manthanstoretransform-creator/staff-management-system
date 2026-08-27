import React, { useState, useMemo } from "react";
import { V2Shell } from "../dashboard/v2/V2Shell";
import {
  useGetAllProjectsQuery,
  useGetProjectMetadataQuery,
  useGetAssignableEmployeesQuery,
  useCreateTaskMutation,
  useUpdateTaskMutation,
} from "../../store/api/projectsApi";
import { useFeedback } from "../../components/FeedbackProvider";
import { InlineRefreshIndicator } from "../../components/InlineRefreshIndicator";

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const day = date.getDate().toString().padStart(2, "0");
  const month = date.toLocaleString("en-US", { month: "short" });
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
};

const getTodayInputValue = () => {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${today.getFullYear()}-${month}-${day}`;
};

const CustomStatusDropdown = ({
  value,
  options,
  onChange,
}: {
  value: number;
  options: any[];
  onChange: (val: number) => void;
}) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const selected = options?.find((o) => o.id === value) || options?.[0];

  return (
    <div className="relative inline-block min-w-[120px]">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold shadow-sm outline-none transition focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6]"
      >
        <div className="flex items-center gap-2">
          {selected && (
            <div
              className="h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: selected.color }}
            ></div>
          )}
          <span style={{ color: selected?.color || "#334155" }}>
            {selected?.task_status || "Select"}
          </span>
        </div>
        <svg
          className="h-3 w-3 text-slate-400"
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
      </button>
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          ></div>
          <div className="absolute right-0 top-full z-20 mt-1 w-full min-w-[120px] overflow-hidden rounded-md border border-slate-200 bg-white shadow-xl">
            {options?.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  onChange(opt.id);
                  setIsOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-bold transition hover:bg-slate-50"
                style={{ color: opt.color }}
              >
                <div
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: opt.color }}
                ></div>
                {opt.task_status}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export const AdminTaskListing: React.FC = () => {
  const { showToast } = useFeedback();
  const [search, setSearch] = useState("");
  const [filterStatusId, setFilterStatusId] = useState<number | null>(null);
  const [filterProjectId, setFilterProjectId] = useState<number | null>(null);
  const [filterDate, setFilterDate] = useState(getTodayInputValue);

  const { data: metadata } = useGetProjectMetadataQuery();
  const { data: employeesData } = useGetAssignableEmployeesQuery();
  const { data: projects, isLoading, isFetching } = useGetAllProjectsQuery();

  // Rows stay on screen while a refetch runs; task edits are applied to the
  // cache optimistically, so neither needs a blocking overlay.
  const showFirstLoad = isLoading && !projects;
  const [createTask] = useCreateTaskMutation();
  const [updateTask, { isLoading: isUpdatingTask }] = useUpdateTaskMutation();

  // Create Task Drawer State
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [formProjectId, setFormProjectId] = useState<number | "">("");
  const [formTaskName, setFormTaskName] = useState("");
  const [formAssigneeId, setFormAssigneeId] = useState<number | "">("");
  const [formStatusId, setFormStatusId] = useState<number>(1);

  // Expanded employee sections
  const [expandedEmployees, setExpandedEmployees] = useState<
    Record<number, boolean>
  >({});

  const toggleEmployee = (empId: number) => {
    setExpandedEmployees((prev) => ({
      ...prev,
      [empId]: prev[empId] === undefined ? false : !prev[empId],
    }));
  };

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
      showToast("Task created successfully.", "success");
    } catch (err) {
      console.error(err);
      showToast("Unable to create task. Please try again.", "error");
    }
  };

  const handleUpdateTaskStatus = async (
    projectId: number,
    taskId: number,
    newStatusId: number,
  ) => {
    try {
      await updateTask({
        projectId,
        taskId,
        body: { status_id: newStatusId },
      }).unwrap();
    } catch (err) {
      console.error(err);
    }
  };

  // Group tasks by assignee
  const groupedTasks = useMemo(() => {
    if (!projects) return [];

    const employeeMap = new Map<number, {
      id: number;
      name: string;
      tasks: any[];
      completedCount: number;
      initials: string;
    }>();
    const normalizedSearch = search.trim().toLowerCase();

    projects.forEach((project) => {
      if (filterProjectId !== null && project.id !== filterProjectId) return;

      project.tasks?.forEach((task) => {
        if (filterStatusId && task.status?.id !== filterStatusId) return;
        if (filterDate && !task.created_at.startsWith(filterDate)) return;
        const empName = task.assignee?.name || "Unassigned";
        if (normalizedSearch && ![task.name, project.project_name, empName]
          .some((value) => value.toLowerCase().includes(normalizedSearch))) return;

        const empId = task.assignee?.id || 0;

        if (!employeeMap.has(empId)) {
          employeeMap.set(empId, {
            id: empId,
            name: empName,
            tasks: [],
            completedCount: 0,
            initials:
              empName === "Unassigned"
                ? "?"
                : empName.substring(0, 2).toUpperCase(),
          });
        }

        const empData = employeeMap.get(empId);
        if (!empData) return;
        empData.tasks.push({ ...task, project_name: project.project_name });
        if (task.status?.name === "Completed") {
          empData.completedCount++;
        }
      });
    });

    return Array.from(employeeMap.values()).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [projects, filterDate, filterProjectId, filterStatusId, search]);

  return (
    <V2Shell
      title="V2 Task Listing"
      subtitle="View all tasks grouped by employee and track their hours."
      actions={
        <button
          onClick={() => {
            setFormProjectId("");
            setFormTaskName("");
            setFormAssigneeId("");
            setFormStatusId(metadata?.task_statuses?.[0]?.id || 1);
            setIsDrawerOpen(true);
          }}
          className="rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] px-4 py-2 text-sm font-bold text-white shadow-md transition hover:opacity-90"
        >
          + Add Task
        </button>
      }
    >
      <div className="mx-auto max-w-6xl space-y-8 pb-20">
        {/* Filters Top Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="relative w-full sm:max-w-md">
            <svg
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Search by employee, project, or task..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
            />
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Status:
            </span>
            <select
              value={filterStatusId || ""}
              onChange={(e) =>
                setFilterStatusId(
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
            >
              <option value="">All Statuses</option>
              {metadata?.task_statuses?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.task_status}
                </option>
              ))}
            </select>
            <select
              value={filterProjectId || ""}
              onChange={(e) =>
                setFilterProjectId(e.target.value ? Number(e.target.value) : null)
              }
              className="max-w-[220px] rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 outline-none transition focus:border-[#3B82F6]"
            >
              <option value="">All Projects</option>
              {projects?.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.project_name}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 rounded-lg border border-[#3B82F6] px-3 py-1.5 text-sm font-bold text-[#3B82F6] transition hover:bg-blue-50">
              <span>Created</span>
              <input
                type="date"
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                aria-label="Filter tasks by creation date"
                className="bg-transparent text-sm font-semibold text-slate-700 outline-none"
              />
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </label>
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setFilterStatusId(null);
                setFilterProjectId(null);
                setFilterDate("");
              }}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-bold text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Grouped Tasks */}
        {showFirstLoad ? (
          <div className="flex justify-center p-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
          </div>
        ) : (
          <div className="relative space-y-6">
            <div className="pointer-events-none absolute right-0 -top-9 z-10">
              <InlineRefreshIndicator active={isUpdatingTask || (isFetching && !showFirstLoad)} />
            </div>
            {groupedTasks.map((group) => {
              const isExpanded = expandedEmployees[group.id] !== false; // default true
              return (
                <div
                  key={group.id}
                  className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden transition-all"
                >
                  {/* Header */}
                  <div
                    onClick={() => toggleEmployee(group.id)}
                    className="flex cursor-pointer items-center justify-between bg-slate-50 p-6 transition hover:bg-slate-100"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] text-sm font-bold text-white shadow-sm">
                        {group.initials}
                      </div>
                      <div>
                        <h3 className="text-lg font-black text-slate-800">
                          {group.name}
                        </h3>
                        <p className="text-xs font-semibold text-slate-500">
                          {group.tasks.length} Assigned Tasks &bull;{" "}
                          {group.completedCount} Completed
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
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
                      {group.tasks.map((task: any) => (
                        <div
                          key={task.id}
                          className="flex items-center justify-between p-6 transition hover:bg-slate-50/50"
                        >
                          <div className="flex items-start gap-4">
                            {task.status?.name === "Completed" ? (
                              <svg
                                className="mt-0.5 h-5 w-5 text-[#10B981]"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2"
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                            ) : task.status?.name === "In Progress" ? (
                              <svg
                                className="mt-0.5 h-5 w-5 text-[#3B82F6]"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2"
                                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                                />
                              </svg>
                            ) : (
                              <div className="mt-1 h-3.5 w-3.5 rounded-full border-2 border-slate-300"></div>
                            )}
                            <div>
                              <div className="flex items-center gap-2">
                                <h4 className="font-bold text-slate-800">
                                  {task.name}
                                </h4>
                                <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-600 border border-indigo-100">
                                  {task.project_name}
                                </span>
                              </div>
                              <div className="mt-1 flex items-center gap-2 text-xs font-semibold text-slate-500">
                                <span>{formatDate(task.created_at)}</span>
                              </div>
                            </div>
                          </div>
                          <div>
                            <div>
                              <CustomStatusDropdown
                                value={task.status?.id || 1}
                                options={metadata?.task_statuses || []}
                                onChange={(val) =>
                                  handleUpdateTaskStatus(
                                    task.project_id,
                                    task.id,
                                    val,
                                  )
                                }
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
            {groupedTasks.length === 0 && (
              <div className="py-20 text-center border-2 border-dashed border-slate-200 rounded-xl">
                <p className="text-slate-500 font-medium">No tasks found.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Task Drawer */}
      <div
        className={`fixed inset-0 z-50 overflow-hidden ${isDrawerOpen ? "pointer-events-auto" : "pointer-events-none"}`}
      >
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
                  Assign a new task to an employee
                </p>
              </div>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="rounded-full p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-600"
              >
                <svg
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              <form
                id="task-form"
                onSubmit={handleCreateTask}
                className="space-y-6"
              >
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                    Project
                  </label>
                  <select
                    required
                    value={formProjectId}
                    onChange={(e) => setFormProjectId(Number(e.target.value))}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6]"
                  >
                    <option value="">Select a project...</option>
                    {projects?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.project_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                    Task Name
                  </label>
                  <input
                    type="text"
                    required
                    value={formTaskName}
                    onChange={(e) => setFormTaskName(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6]"
                    placeholder="e.g. Design UI Mockups"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                    Assignee
                  </label>
                  <select
                    value={formAssigneeId}
                    onChange={(e) =>
                      setFormAssigneeId(
                        e.target.value ? Number(e.target.value) : "",
                      )
                    }
                    className="w-full rounded-lg border border-slate-300 px-4 py-2.5 bg-white text-sm font-medium text-slate-700 outline-none focus:border-[#3B82F6]"
                  >
                    <option value="">Unassigned</option>
                    {employeesData?.map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                    Status
                  </label>
                  <div className="w-full">
                    <CustomStatusDropdown
                      value={formStatusId}
                      options={metadata?.task_statuses || []}
                      onChange={(val) => setFormStatusId(val)}
                    />
                  </div>
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
                className="flex-1 rounded-lg bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] py-3 text-sm font-bold text-white transition hover:opacity-90"
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
