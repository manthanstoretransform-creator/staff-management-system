import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/authContext";
import { listProjectsAPI } from "../../api/project";
import type { ProjectRead } from "../../api/project";
import { listTasksAPI, createTaskAPI, updateTaskAPI, archiveTaskAPI } from "../../api/task";
import type { TaskRead, TaskCreate, TaskUpdate } from "../../api/task";
import { createManualTimeEntryAPI, listManualTimeEntriesAPI, listProjectManualTimeEntriesAPI } from "../../api/manualTimeEntry";
import type { ManualTimeEntryRead, ManualTimeEntryCreate } from "../../api/manualTimeEntry";
import { startTimerAPI, stopTimerAPI, listProjectTimeEntriesAPI } from "../../api/timeEntry";
import type { TimeEntryRead } from "../../api/timeEntry";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const ProjectList: React.FC = () => {
  const { accessToken, currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const getInitials = (name: string) => {
    if (!name) return "ST";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };
  
  // Projects State
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tasks State
  const [tasks, setTasks] = useState<TaskRead[]>([]);
  const [isTasksLoading, setIsTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  // Task Creation Modal State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [taskName, setTaskName] = useState("");
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [estimatedHours, setEstimatedHours] = useState("");
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [assignToSelf, setAssignToSelf] = useState(false);

  // Task Details Modal State
  const [selectedTask, setSelectedTask] = useState<TaskRead | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  // Manual Time Entry State
  const [manualEntries, setManualEntries] = useState<ManualTimeEntryRead[]>([]);
  const [isManualLoading, setIsManualLoading] = useState(false);
  const [isManualFormOpen, setIsManualFormOpen] = useState(false);
  const [manualDate, setManualDate] = useState(new Date().toISOString().split("T")[0]);
  const [manualHours, setManualHours] = useState("");
  const [manualMinutes, setManualMinutes] = useState("");
  const [manualIsBillable, setManualIsBillable] = useState(true);
  const [manualError, setManualError] = useState<string | null>(null);
  const [isLoggingManual, setIsLoggingManual] = useState(false);

  // Automatic Timer State
  const [activeTimer, setActiveTimer] = useState<TimeEntryRead | null>(null);
  const [isTimerLoading, setIsTimerLoading] = useState(false);
  const [timerError, setTimerError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Project-level Time Entries for client-side summation
  const [projectTimeEntries, setProjectTimeEntries] = useState<TimeEntryRead[]>([]);
  const [projectManualEntries, setProjectManualEntries] = useState<ManualTimeEntryRead[]>([]);
  const [allTimeEntries, setAllTimeEntries] = useState<TimeEntryRead[]>([]);
  const [allManualEntries, setAllManualEntries] = useState<ManualTimeEntryRead[]>([]);

  // Three-dot menu state per task
  const [activeMenuTaskId, setActiveMenuTaskId] = useState<number | null>(null);

  // Archive confirmation state
  const [taskToArchive, setTaskToArchive] = useState<TaskRead | null>(null);
  const [isArchiving, setIsArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  // Close menus on clicking outside
  useEffect(() => {
    const handleOutsideClick = () => {
      setActiveMenuTaskId(null);
    };
    window.addEventListener("click", handleOutsideClick);
    return () => window.removeEventListener("click", handleOutsideClick);
  }, []);

  // Fetch Projects on mount/token change
  useEffect(() => {
    let isMounted = true;

    const fetchProjects = async () => {
      if (!accessToken) {
        navigate("/login");
        return;
      }

      try {
        const data = await listProjectsAPI(accessToken);
        if (isMounted) {
          setProjects(data);
          if (data.length > 0) {
            setSelectedProject(data[0]);
          }
          setIsLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          if (err.message === "Unauthorized") {
            logout();
            navigate("/login");
          } else {
            setError(err.message || "Failed to load projects.");
            setIsLoading(false);
          }
        }
      }
    };

    fetchProjects();

    return () => {
      isMounted = false;
    };
  }, [accessToken, navigate, logout]);

  // Fetch Tasks when selected project changes or refetch triggered
  useEffect(() => {
    if (!selectedProject || !accessToken) {
      setTasks([]);
      return;
    }

    let isMounted = true;
    setIsTasksLoading(true);
    setTasksError(null);

    const fetchTasks = async () => {
      try {
        const data = await listTasksAPI(accessToken, selectedProject.id);
        if (isMounted) {
          setTasks(data);
          setIsTasksLoading(false);
          
          // Keep detail view updated if task details are open
          if (selectedTask) {
            const updatedTask = data.find((t) => t.id === selectedTask.id);
            if (updatedTask) {
              setSelectedTask(updatedTask);
            }
          }
        }
      } catch (err: any) {
        if (isMounted) {
          if (err.message === "Unauthorized") {
            logout();
            navigate("/login");
          } else {
            setTasksError(err.message || "Failed to load tasks.");
            setIsTasksLoading(false);
          }
        }
      }
    };

    fetchTasks();

    return () => {
      isMounted = false;
    };
  }, [selectedProject, accessToken, navigate, logout, refetchTrigger]);

  // Fetch all project-level time entries (automatic & manual) to compute client-side totals
  useEffect(() => {
    if (!selectedProject || !accessToken) {
      setProjectTimeEntries([]);
      setProjectManualEntries([]);
      return;
    }

    let isMounted = true;

    const fetchProjectTimeData = async () => {
      try {
        const [timeEntries, manualEntries] = await Promise.all([
          listProjectTimeEntriesAPI(accessToken, selectedProject.id),
          listProjectManualTimeEntriesAPI(accessToken, selectedProject.id)
        ]);
        if (isMounted) {
          setProjectTimeEntries(timeEntries);
          setProjectManualEntries(manualEntries);
        }
      } catch (err: any) {
        console.error("Failed to load project time entries:", err);
      }
    };

    fetchProjectTimeData();

    return () => {
      isMounted = false;
    };
  }, [selectedProject?.id, accessToken, refetchTrigger]);

  // Fetch ALL time entries for the logged-in employee across all projects
  useEffect(() => {
    if (!accessToken) {
      setAllTimeEntries([]);
      setAllManualEntries([]);
      return;
    }

    let isMounted = true;

    const fetchAllTimeData = async () => {
      try {
        const [timeRes, manualRes] = await Promise.all([
          fetch(`${API_BASE_URL}/time-entries?limit=1000`, {
            headers: { "Authorization": `Bearer ${accessToken}` }
          }),
          fetch(`${API_BASE_URL}/manual-time-entries?limit=1000`, {
            headers: { "Authorization": `Bearer ${accessToken}` }
          })
        ]);

        if (timeRes.ok && manualRes.ok) {
          const timeData = await timeRes.json();
          const manualData = await manualRes.json();
          if (isMounted) {
            setAllTimeEntries(timeData);
            setAllManualEntries(manualData);
          }
        }
      } catch (err) {
        console.error("Failed to fetch all time entries:", err);
      }
    };

    fetchAllTimeData();

    return () => {
      isMounted = false;
    };
  }, [accessToken, refetchTrigger]);

  // Fetch manual time entries when selectedTask changes
  useEffect(() => {
    if (!selectedTask || !accessToken) {
      setManualEntries([]);
      setIsManualFormOpen(false);
      return;
    }

    let isMounted = true;
    setIsManualLoading(true);
    setManualError(null);

    const fetchManualEntries = async () => {
      try {
        const data = await listManualTimeEntriesAPI(accessToken, selectedTask.id);
        if (isMounted) {
          setManualEntries(data);
          setIsManualLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          if (err.message === "Unauthorized") {
            logout();
            navigate("/login");
          } else {
            setManualError(err.message || "Failed to load manual time entries.");
            setIsManualLoading(false);
          }
        }
      }
    };

    fetchManualEntries();

    return () => {
      isMounted = false;
    };
  }, [selectedTask?.id, accessToken, navigate, logout]);

  const handleLogManualTime = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !accessToken) return;

    if (!manualDate) {
      setManualError("Date worked is required.");
      return;
    }

    const hours = parseInt(manualHours || "0", 10);
    const minutes = parseInt(manualMinutes || "0", 10);
    const total_seconds = hours * 3600 + minutes * 60;

    if (total_seconds <= 0 || total_seconds > 86400) {
      setManualError("Total time worked must be greater than 0 and no more than 24 hours.");
      return;
    }

    setManualError(null);
    setIsLoggingManual(true);

    try {
      const payload: ManualTimeEntryCreate = {
        project_id: selectedTask.project_id,
        task_id: selectedTask.id,
        work_date: manualDate,
        total_seconds,
        is_billable: manualIsBillable,
      };

      await createManualTimeEntryAPI(accessToken, payload);
      
      // Reset form states
      setManualHours("");
      setManualMinutes("");
      setManualDate(new Date().toISOString().split("T")[0]);
      setIsManualFormOpen(false);
      setIsLoggingManual(false);

      // Refetch manual list and task list to update tracked total time
      const updatedEntries = await listManualTimeEntriesAPI(accessToken, selectedTask.id);
      setManualEntries(updatedEntries);
      setRefetchTrigger((prev) => prev + 1);
    } catch (err: any) {
      setIsLoggingManual(false);
      if (err.message === "Unauthorized") {
        logout();
        navigate("/login");
      } else {
        setManualError(err.message || "Failed to log manual time.");
      }
    }
  };

  const getTaskTrackedSeconds = (taskId: number): number => {
    const autoSeconds = projectTimeEntries
      .filter((e) => e.task_id === taskId && e.status === "stopped")
      .reduce((sum, e) => sum + e.total_seconds, 0);

    const manualSeconds = projectManualEntries
      .filter((e) => e.task_id === taskId && e.approval_status === "approved")
      .reduce((sum, e) => sum + e.total_seconds, 0);

    return autoSeconds + manualSeconds;
  };

  const getProjectTrackedSeconds = (projectId: number): number => {
    const autoSeconds = allTimeEntries
      .filter((e) => e.project_id === projectId && e.status === "stopped")
      .reduce((sum, e) => sum + e.total_seconds, 0);

    const manualSeconds = allManualEntries
      .filter((e) => e.project_id === projectId && e.approval_status === "approved")
      .reduce((sum, e) => sum + e.total_seconds, 0);

    return autoSeconds + manualSeconds;
  };

  // Fetch active timer for the current user globally on mount / refetch trigger
  useEffect(() => {
    if (!accessToken) {
      setActiveTimer(null);
      setTimerError(null);
      return;
    }

    let isMounted = true;
    setIsTimerLoading(true);
    setTimerError(null);

    const checkActiveTimer = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/time-entries?status=running&user_id=${currentUser?.id || ""}`, {
          headers: { "Authorization": `Bearer ${accessToken}` }
        });
        if (response.ok) {
          const entries = await response.json();
          if (isMounted) {
            if (entries && entries.length > 0) {
              setActiveTimer(entries[0]);
            } else {
              setActiveTimer(null);
            }
            setIsTimerLoading(false);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          if (err.message === "Unauthorized") {
            logout();
            navigate("/login");
          } else {
            setTimerError(err.message || "Failed to check running timer.");
            setIsTimerLoading(false);
          }
        }
      }
    };

    checkActiveTimer();

    return () => {
      isMounted = false;
    };
  }, [accessToken, navigate, logout, refetchTrigger]);

  // Live ticking counter
  useEffect(() => {
    if (!activeTimer) {
      setElapsedSeconds(0);
      return;
    }

    const startTimeMs = new Date(activeTimer.start_time).getTime();

    const updateCounter = () => {
      const nowMs = new Date().getTime();
      const diffSec = Math.max(0, Math.floor((nowMs - startTimeMs) / 1000));
      setElapsedSeconds(diffSec);
    };

    updateCounter();
    const interval = setInterval(updateCounter, 1000);

    return () => {
      clearInterval(interval);
    };
  }, [activeTimer]);

  const formatSeconds = (totalSeconds: number): string => {
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return [
      hrs.toString().padStart(2, "0"),
      mins.toString().padStart(2, "0"),
      secs.toString().padStart(2, "0")
    ].join(":");
  };

  const handleStartTimer = async (task: TaskRead) => {
    if (!accessToken) return;

    setTimerError(null);
    setIsTimerLoading(true);

    try {
      const entry = await startTimerAPI(accessToken, task.project_id, task.id);
      setActiveTimer(entry);
      setIsTimerLoading(false);
      setRefetchTrigger((prev) => prev + 1);
    } catch (err: any) {
      setIsTimerLoading(false);
      if (err.message === "Unauthorized") {
        logout();
        navigate("/login");
      } else {
        setTimerError(err.message || "Failed to start timer.");
      }
    }
  };

  const handleStopTimer = async () => {
    if (!activeTimer || !accessToken) return;

    setTimerError(null);
    setIsTimerLoading(true);

    try {
      const stoppedEntry = await stopTimerAPI(accessToken, activeTimer.id);
      setActiveTimer(null);
      setIsTimerLoading(false);

      // Update the local projectTimeEntries state
      setProjectTimeEntries((prev) => {
        const filtered = prev.filter((e) => e.id !== stoppedEntry.id);
        return [...filtered, stoppedEntry];
      });

      setRefetchTrigger((prev) => prev + 1);
    } catch (err: any) {
      setIsTimerLoading(false);
      if (err.message === "Unauthorized") {
        logout();
        navigate("/login");
      } else if (err.message && err.message.includes("Conflict: Already stopped")) {
        setActiveTimer(null);
        setRefetchTrigger((prev) => prev + 1);
      } else {
        setTimerError(err.message || "Failed to stop timer.");
      }
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleOpenCreateModal = () => {
    setTaskName("");
    setDescription("");
    setStartDate("");
    setDueDate("");
    setEstimatedHours("");
    setAssignToSelf(false);
    setCreateFormError(null);
    setIsCreateModalOpen(true);
  };

  const handleCloseCreateModal = () => {
    setIsCreateModalOpen(false);
  };

  const handleCreateTaskSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !accessToken) return;

    if (!taskName.trim()) {
      setCreateFormError("Task name is required.");
      return;
    }

    setCreateFormError(null);
    setIsCreating(true);

    try {
      const isAdminUser = currentUser && ["admin", "org_admin", "super_admin"].includes(currentUser.role_name);
      const taskPayload: TaskCreate = {
        task_name: taskName.trim(),
        description: description.trim() || undefined,
        start_date: startDate || undefined,
        due_date: dueDate || undefined,
        estimated_hours: estimatedHours ? parseFloat(estimatedHours) : undefined,
        assignee_id: (isAdminUser && assignToSelf) ? currentUser.id : undefined,
      };

      await createTaskAPI(accessToken, selectedProject.id, taskPayload);
      setIsCreating(false);
      setIsCreateModalOpen(false);
      setRefetchTrigger((prev) => prev + 1);
    } catch (err: any) {
      setIsCreating(false);
      if (err.message === "Unauthorized") {
        logout();
        navigate("/login");
      } else {
        setCreateFormError(err.message || "Failed to create task.");
      }
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!selectedProject || !selectedTask || !accessToken) return;

    setDetailError(null);
    setIsUpdatingStatus(true);

    try {
      const updatePayload: TaskUpdate = {
        status: newStatus,
      };

      const updatedTask = await updateTaskAPI(accessToken, selectedProject.id, selectedTask.id, updatePayload);
      setSelectedTask(updatedTask);
      setIsUpdatingStatus(false);
      setRefetchTrigger((prev) => prev + 1);
    } catch (err: any) {
      setIsUpdatingStatus(false);
      if (err.message === "Unauthorized") {
        logout();
        navigate("/login");
      } else {
        setDetailError(err.message || "Failed to update task status.");
      }
    }
  };

  const handleArchiveConfirm = async () => {
    if (!selectedProject || !taskToArchive || !accessToken) return;

    setArchiveError(null);
    setIsArchiving(true);

    try {
      await archiveTaskAPI(accessToken, selectedProject.id, taskToArchive.id);
      setIsArchiving(false);
      
      // Close details modal if the archived task was currently selected
      if (selectedTask?.id === taskToArchive.id) {
        setSelectedTask(null);
      }
      
      setTaskToArchive(null);
      setRefetchTrigger((prev) => prev + 1);
    } catch (err: any) {
      setIsArchiving(false);
      if (err.message === "Unauthorized") {
        logout();
        navigate("/login");
      } else {
        setArchiveError(err.message || "Failed to archive task.");
      }
    }
  };

  const formatTrackedTime = (seconds: number): string => {
    const hours = seconds / 3600;
    return `${hours.toFixed(1)}h`;
  };

  const formatDate = (dateStr?: string): string => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatDateTime = (dateTimeStr?: string): string => {
    if (!dateTimeStr) return "N/A";
    return new Date(dateTimeStr).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Color dots based on project status
  const getStatusDotColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "active":
        return "bg-green-500";
      case "archived":
        return "bg-slate-400";
      case "planning":
        return "bg-blue-500";
      default:
        return "bg-purple-500";
    }
  };

  const getStatusBadgeStyles = (status: string) => {
    switch (status.toLowerCase()) {
      case "active":
        return "bg-green-50 text-green-700 border-green-200";
      case "archived":
        return "bg-slate-100 text-slate-600 border-slate-200";
      case "planning":
        return "bg-blue-50 text-blue-700 border-blue-200";
      default:
        return "bg-purple-50 text-purple-700 border-purple-200";
    }
  };

  const getTaskStatusBadgeStyles = (status: string) => {
    switch (status.toLowerCase()) {
      case "completed":
        return "bg-green-50 text-green-700 border-green-200";
      case "in_progress":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "todo":
        return "bg-slate-50 text-slate-600 border-slate-200";
      case "archived":
        return "bg-slate-100 text-slate-500 border-slate-200";
      default:
        return "bg-slate-50 text-slate-600 border-slate-200";
    }
  };

  // Active tasks only
  const activeTasks = tasks.filter((t) => t.status.toLowerCase() !== "archived");

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-sans">
      {/* Sidebar - dark theme (#0B1220) */}
      <aside className="w-[290px] bg-[#0B1220] text-white flex flex-col justify-between p-6 shrink-0 h-screen sticky top-0 overflow-y-auto">
        <div className="flex flex-col min-h-0 flex-grow">
          {/* Logo Section */}
          <div className="flex items-center gap-3 mb-8 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#2563EB] to-purple-600 flex items-center justify-center font-bold text-white shadow-md text-lg">
              S
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              StaffTrack
            </span>
          </div>

          {/* Admin Navigation (visible to Admin only) */}
          {currentUser && (currentUser.role_name === "admin" || currentUser.role_name === "org_admin" || currentUser.role_name === "super_admin") && (
            <div className="mb-6 shrink-0 space-y-1">
              <div className="text-[10px] font-semibold text-[#64748B] tracking-wider uppercase mb-2 px-1">
                Admin Panel
              </div>
              <button
                onClick={() => navigate("/admin")}
                className="w-full text-left px-3.5 py-2.5 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
              >
                <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <span>Admin Dashboard</span>
              </button>
              <button
                onClick={() => navigate("/admin/projects")}
                className="w-full text-left px-3.5 py-2.5 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
              >
                <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span>Manage Projects</span>
              </button>
              <button
                onClick={() => navigate("/admin/tasks")}
                className="w-full text-left px-3.5 py-2.5 rounded-lg text-[#94A3B8] hover:text-white hover:bg-slate-800/40 transition duration-150 flex items-center gap-3 cursor-pointer font-medium text-sm leading-snug"
              >
                <svg className="w-5 h-5 text-[#2563EB]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <span>Task Listing</span>
              </button>
            </div>
          )}

          {/* Project List Header */}
          <div className="text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-3 shrink-0">
            Projects
          </div>

          {/* Project Navigation List */}
          <div className="flex-grow overflow-y-auto min-h-0 space-y-1 pr-1">
            {isLoading ? (
              <div className="py-4 text-center text-sm text-[#94A3B8] flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Loading...</span>
              </div>
            ) : projects.length === 0 ? (
              <div className="py-4 text-left text-sm text-[#94A3B8] italic">
                No projects found
              </div>
            ) : (
              projects.map((project) => {
                const isSelected = selectedProject?.id === project.id;
                return (
                  <button
                    key={project.id}
                    onClick={() => setSelectedProject(project)}
                    className={`w-full text-left px-3.5 py-3 rounded-lg transition duration-150 flex items-start gap-3 cursor-pointer ${
                      isSelected
                        ? "bg-[#2563EB] text-white shadow-sm"
                        : "text-[#94A3B8] hover:text-white hover:bg-slate-800/40"
                    }`}
                  >
                    {/* Status indicator dot */}
                    <span className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${getStatusDotColor(project.status)}`} />
                    <div className="min-w-0 flex-grow">
                      <div className="font-medium text-sm truncate leading-snug">
                        {project.project_name}
                      </div>
                      <div className={`text-[11px] mt-0.5 font-bold ${isSelected ? "text-blue-100" : "text-[#64748B] group-hover:text-white/80"}`}>
                        Tracked: {formatTrackedTime(getProjectTrackedSeconds(project.id))}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Pinned Sign Out Section */}
        <div className="pt-4 border-t border-slate-800 shrink-0 space-y-4">
          {currentUser && (
            <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-700/40 flex items-center gap-3">
              {/* Avatar circle */}
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

      {/* Main Content Area */}
      <div className="flex-grow flex flex-col min-w-0">
        {/* Header bar */}
        <header className="h-16 border-b border-[#E2E8F0] bg-white px-8 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-[#0F172A]">
            {selectedProject ? selectedProject.project_name : "Dashboard"}
          </h1>
        </header>

        {/* Content */}
        <main className="flex-grow p-8 overflow-y-auto space-y-8">
          {isLoading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-3">
              <svg className="animate-spin h-8 w-8 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-sm text-[#64748B]">Loading workspace data...</span>
            </div>
          ) : error ? (
            <div className="max-w-md mx-auto bg-white p-6 rounded-xl border border-red-100 shadow-sm text-center">
              <div className="w-12 h-12 bg-red-50 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-[#0F172A] mb-1">Failed to load data</h3>
              <p className="text-sm text-[#64748B] mb-4">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-[#2563EB] hover:bg-blue-700 text-white text-sm font-semibold rounded-md shadow-sm transition"
              >
                Retry
              </button>
            </div>
          ) : projects.length === 0 ? (
            /* Empty State Container */
            <div className="max-w-md mx-auto bg-white p-8 rounded-xl border border-[#E2E8F0] shadow-sm text-center mt-12">
              <div className="w-16 h-16 bg-blue-50 text-[#2563EB] rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-[#0F172A] mb-2">No projects yet</h2>
              <p className="text-sm text-[#64748B]">
                There are no projects registered in your organization yet.
              </p>
            </div>
          ) : selectedProject ? (
            <>
              {/* Detailed Card for Selected Project */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
                <div className="p-8">
                  <div className="flex items-center justify-between gap-4 mb-6">
                    <h2 className="text-2xl font-bold text-[#0F172A]">
                      {selectedProject.project_name}
                    </h2>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusBadgeStyles(selectedProject.status)} capitalize`}>
                      {selectedProject.status}
                    </span>
                  </div>

                  {selectedProject.description ? (
                    <p className="text-base text-[#64748B] mb-8 leading-relaxed">
                      {selectedProject.description}
                    </p>
                  ) : (
                    <p className="text-sm text-[#94A3B8] italic mb-8">
                      No description provided for this project.
                    </p>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-6 border-t border-[#F1F5F9] text-sm">
                    <div className="flex flex-col gap-1">
                      <span className="text-[#94A3B8] text-xs font-semibold uppercase tracking-wider">
                        Classification
                      </span>
                      <span className={`font-semibold self-start px-2.5 py-0.5 rounded text-xs ${selectedProject.is_billable ? "bg-amber-50 text-amber-700 border border-amber-200" : "bg-slate-50 text-slate-600 border border-slate-200"}`}>
                        {selectedProject.is_billable ? "Billable" : "Non-Billable"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-[#94A3B8] text-xs font-semibold uppercase tracking-wider">
                        Total Time Tracked
                      </span>
                      <span className="font-bold text-[#0F172A] text-lg">
                        {formatTrackedTime(getProjectTrackedSeconds(selectedProject.id))}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Task List Section */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-[#0F172A] tracking-wide uppercase text-xs">
                    Tasks
                  </h3>
                  <button
                    onClick={handleOpenCreateModal}
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-xs font-semibold text-white bg-[#2563EB] hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2563EB] transition cursor-pointer"
                  >
                    Create Task
                  </button>
                </div>

                {isTasksLoading ? (
                  <div className="h-32 flex flex-col items-center justify-center gap-2 bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
                    <svg className="animate-spin h-6 w-6 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span className="text-xs text-[#64748B]">Loading tasks...</span>
                  </div>
                ) : tasksError ? (
                  <div className="p-6 bg-white rounded-xl border border-[#E2E8F0] shadow-sm text-center">
                    <span className="text-sm text-red-600">{tasksError}</span>
                  </div>
                ) : activeTasks.length === 0 ? (
                  <div className="max-w-md mx-auto bg-white p-8 rounded-xl border border-[#E2E8F0] shadow-sm text-center">
                    <div className="w-12 h-12 bg-blue-50 text-[#2563EB] rounded-full flex items-center justify-center mx-auto mb-3">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                    </div>
                    <h4 className="text-sm font-semibold text-[#0F172A] mb-1">No tasks yet in this project</h4>
                    <p className="text-xs text-[#64748B]">Tasks added to this project will show up here.</p>
                  </div>
                ) : (
                  <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden divide-y divide-[#F1F5F9]">
                    {activeTasks.map((task) => (
                      <div
                        key={task.id}
                        onClick={() => setSelectedTask(task)}
                        className="p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 hover:bg-slate-50/50 cursor-pointer transition relative group"
                      >
                        <div className="min-w-0 pr-12">
                          <div className="flex items-center gap-3 mb-1">
                            <span className="font-semibold text-sm text-[#0F172A] truncate">
                              {task.task_name}
                            </span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${getTaskStatusBadgeStyles(task.status)} capitalize shrink-0`}>
                              {task.status.replace("_", " ")}
                            </span>
                          </div>
                          {task.description && (
                            <p className="text-xs text-[#64748B] line-clamp-1">
                              {task.description}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-4 shrink-0 text-xs text-[#94A3B8] sm:pr-8 z-10">
                          {task.estimated_hours !== null && (
                            <div>
                              Est: <span className="font-medium text-[#64748B]">{task.estimated_hours}h</span>
                            </div>
                          )}
                          <div className="mr-2">
                            Tracked: <span className="font-bold text-[#0F172A]">{formatTrackedTime(getTaskTrackedSeconds(task.id))}</span>
                          </div>
                          {activeTimer && activeTimer.task_id === task.id ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleStopTimer();
                              }}
                              disabled={isTimerLoading}
                              className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white font-semibold text-xs rounded-lg transition duration-150 shadow-sm cursor-pointer disabled:opacity-50"
                            >
                              Stop Timer
                            </button>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleStartTimer(task);
                              }}
                              disabled={isTimerLoading}
                              className="px-3 py-1.5 bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition duration-150 shadow-sm cursor-pointer disabled:opacity-50"
                            >
                              Start Timer
                            </button>
                          )}
                        </div>

                        {/* Three-dot menu button */}
                        <div className="absolute right-4 top-1/2 -translate-y-1/2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveMenuTaskId(activeMenuTaskId === task.id ? null : task.id);
                            }}
                            className="p-1 rounded-md hover:bg-slate-100 text-[#94A3B8] hover:text-[#64748B] cursor-pointer"
                          >
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                            </svg>
                          </button>

                          {/* Dropdown Menu */}
                          {activeMenuTaskId === task.id && (
                            <div
                              onClick={(e) => e.stopPropagation()}
                              className="absolute right-0 mt-1 w-36 bg-white rounded-md border border-[#E2E8F0] shadow-lg py-1 z-10"
                            >
                              <button
                                onClick={() => setTaskToArchive(task)}
                                className="w-full text-left px-4 py-2 text-xs text-red-600 hover:bg-red-50 transition font-medium cursor-pointer"
                              >
                                Archive Task
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="text-sm text-[#94A3B8] italic">
              Select a project from the sidebar to view details.
            </div>
          )}
        </main>
      </div>

      {/* Modal - Create Task */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="relative bg-white rounded-xl shadow-xl border border-[#E2E8F0] max-w-md w-full overflow-hidden p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-4">
              <h3 className="text-lg font-bold text-[#0F172A]">Create Task</h3>
              <button
                onClick={handleCloseCreateModal}
                className="text-[#94A3B8] hover:text-[#64748B] cursor-pointer"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCreateTaskSubmit} className="space-y-4">
              {createFormError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
                  {createFormError}
                </div>
              )}

              <div>
                <label htmlFor="taskName" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                  Task Name *
                </label>
                <input
                  id="taskName"
                  type="text"
                  required
                  disabled={isCreating}
                  value={taskName}
                  onChange={(e) => setTaskName(e.target.value)}
                  placeholder="e.g. Design Landing Page"
                  className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A]"
                />
              </div>

              <div>
                <label htmlFor="description" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                  Description
                </label>
                <textarea
                  id="description"
                  rows={3}
                  disabled={isCreating}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Provide details about the task..."
                  className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A]"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="startDate" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Start Date
                  </label>
                  <input
                    id="startDate"
                    type="date"
                    disabled={isCreating}
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A]"
                  />
                </div>
                <div>
                  <label htmlFor="dueDate" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Due Date
                  </label>
                  <input
                    id="dueDate"
                    type="date"
                    disabled={isCreating}
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A]"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="estimatedHours" className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                  Estimated Hours
                </label>
                <input
                  id="estimatedHours"
                  type="number"
                  step="0.1"
                  min="0"
                  disabled={isCreating}
                  value={estimatedHours}
                  onChange={(e) => setEstimatedHours(e.target.value)}
                  placeholder="e.g. 8.5"
                  className="w-full px-3 py-2 border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A]"
                />
              </div>

              {currentUser && ["admin", "org_admin", "super_admin"].includes(currentUser.role_name) && (
                <div className="flex items-center gap-3 p-3 bg-slate-50 border border-slate-200/60 rounded-lg">
                  <input
                    id="assignToSelf"
                    type="checkbox"
                    disabled={isCreating}
                    checked={assignToSelf}
                    onChange={(e) => setAssignToSelf(e.target.checked)}
                    className="w-4 h-4 text-[#2563EB] rounded border-gray-300 cursor-pointer focus:ring-[#2563EB]"
                  />
                  <label htmlFor="assignToSelf" className="text-xs font-bold text-slate-700 select-none cursor-pointer">
                    Assign this task to myself
                  </label>
                </div>
              )}

              <div className="pt-4 border-t border-[#F1F5F9] flex items-center justify-end gap-3">
                <button
                  type="button"
                  disabled={isCreating}
                  onClick={handleCloseCreateModal}
                  className="px-4 py-2 border border-[#E2E8F0] rounded-md text-sm font-semibold text-[#64748B] hover:bg-slate-50 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-semibold text-white bg-[#2563EB] hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#2563EB] transition cursor-pointer flex items-center gap-2"
                >
                  {isCreating ? (
                    <>
                      <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Creating...
                    </>
                  ) : (
                    "Create Task"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal - Task Details */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="relative bg-white rounded-xl shadow-xl border border-[#E2E8F0] max-w-lg w-full overflow-hidden p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-4">
              <h3 className="text-lg font-bold text-[#0F172A] truncate max-w-[80%]">
                {selectedTask.task_name}
              </h3>
              <button
                onClick={() => setSelectedTask(null)}
                className="text-[#94A3B8] hover:text-[#64748B] cursor-pointer"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {detailError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
                {detailError}
              </div>
            )}

            <div className="space-y-4 text-sm text-[#64748B]">
              {selectedTask.description && (
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Description
                  </span>
                  <p className="bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0] leading-relaxed text-[#0F172A]">
                    {selectedTask.description}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Status
                  </span>
                  <div className="relative">
                    <select
                      disabled={isUpdatingStatus}
                      value={selectedTask.status}
                      onChange={(e) => handleStatusChange(e.target.value)}
                      className="w-full px-3 py-2 bg-white border border-[#E2E8F0] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-[#2563EB] text-sm text-[#0F172A] capitalize disabled:opacity-50"
                    >
                      <option value="todo">To Do</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                    </select>
                    {isUpdatingStatus && (
                      <span className="absolute right-8 top-2.5">
                        <svg className="animate-spin h-4 w-4 text-[#2563EB]" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Estimated Hours
                  </span>
                  <div className="px-3 py-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-md text-[#0F172A] font-medium">
                    {selectedTask.estimated_hours !== null ? `${selectedTask.estimated_hours}h` : "N/A"}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Start Date
                  </span>
                  <div className="px-3 py-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-md text-[#0F172A]">
                    {formatDate(selectedTask.start_date)}
                  </div>
                </div>
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Due Date
                  </span>
                  <div className="px-3 py-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-md text-[#0F172A]">
                    {formatDate(selectedTask.due_date)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-[#F1F5F9]">
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Time Tracked
                  </span>
                  <div className="font-bold text-[#0F172A] text-lg">
                    {formatTrackedTime(getTaskTrackedSeconds(selectedTask.id))}
                  </div>
                </div>
                <div>
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                    Task ID
                  </span>
                  <div className="font-mono text-[#0F172A] pt-1">
                    #{selectedTask.id}
                  </div>
                </div>
              </div>

              {/* Automatic Timer Controls */}
              <div className="pt-4 border-t border-[#F1F5F9] space-y-3">
                <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase">
                  Automatic Tracking
                </span>
                {timerError && (
                  <div className="p-2 text-xs bg-red-50 border border-red-200 rounded text-red-600">
                    {timerError}
                  </div>
                )}
                {isTimerLoading ? (
                  <div className="text-xs text-[#94A3B8]">Loading timer controls...</div>
                ) : activeTimer ? (
                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 flex items-center justify-between">
                    <div>
                      <div className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Timer Running</div>
                      <div className="font-mono text-2xl font-bold text-blue-900 mt-1">
                        {formatSeconds(elapsedSeconds)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleStopTimer}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold text-xs rounded-lg shadow-sm transition cursor-pointer"
                    >
                      Stop Timer
                    </button>
                  </div>
                ) : (
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-4 flex items-center justify-between">
                    <span className="text-xs text-[#64748B]">No running timer on this task.</span>
                    <button
                      type="button"
                      onClick={() => handleStartTimer(selectedTask)}
                      className="px-4 py-2 bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs rounded-lg shadow-sm transition cursor-pointer"
                    >
                      Start Timer
                    </button>
                  </div>
                )}
              </div>

              {selectedTask.completed_at && (
                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-[#F1F5F9]">
                  <div>
                    <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                      Completed At
                    </span>
                    <div className="text-xs text-[#0F172A]">
                      {formatDateTime(selectedTask.completed_at)}
                    </div>
                  </div>
                  <div>
                    <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase mb-1">
                      Completed By User ID
                    </span>
                    <div className="text-xs text-[#0F172A]">
                      #{selectedTask.completed_by}
                    </div>
                  </div>
                </div>
              )}

              {/* Manual Time Logging and Entries list */}
              <div className="pt-4 border-t border-[#F1F5F9] space-y-4">
                <div className="flex items-center justify-between">
                  <span className="block text-xs font-semibold text-[#94A3B8] tracking-wider uppercase">
                    Manual Logs
                  </span>
                  {!isManualFormOpen && (
                    <button
                      type="button"
                      onClick={() => {
                        setManualError(null);
                        setIsManualFormOpen(true);
                      }}
                      className="text-xs font-semibold text-[#2563EB] hover:text-blue-700 cursor-pointer"
                    >
                      + Log Time Manually
                    </button>
                  )}
                </div>

                {isManualFormOpen && (
                  <form onSubmit={handleLogManualTime} className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-4 space-y-3">
                    {manualError && (
                      <div className="p-2 text-xs bg-red-50 border border-red-200 rounded text-red-600">
                        {manualError}
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-[#64748B] mb-1">Date Worked</label>
                        <input
                          type="date"
                          required
                          max={new Date().toISOString().split("T")[0]}
                          value={manualDate}
                          onChange={(e) => setManualDate(e.target.value)}
                          className="w-full px-2 py-1 text-sm bg-white border border-[#E2E8F0] rounded focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-xs font-semibold text-[#64748B] mb-1">Hours</label>
                          <input
                            type="number"
                            min="0"
                            max="24"
                            placeholder="0"
                            value={manualHours}
                            onChange={(e) => setManualHours(e.target.value)}
                            className="w-full px-2 py-1 text-sm bg-white border border-[#E2E8F0] rounded focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[#64748B] mb-1">Minutes</label>
                          <input
                            type="number"
                            min="0"
                            max="59"
                            placeholder="0"
                            value={manualMinutes}
                            onChange={(e) => setManualMinutes(e.target.value)}
                            className="w-full px-2 py-1 text-sm bg-white border border-[#E2E8F0] rounded focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                          />
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <label className="flex items-center gap-2 text-xs font-semibold text-[#64748B] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={manualIsBillable}
                          onChange={(e) => setManualIsBillable(e.target.checked)}
                          className="rounded text-[#2563EB] focus:ring-[#2563EB] cursor-pointer"
                        />
                        Billable
                      </label>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setIsManualFormOpen(false)}
                          className="px-2.5 py-1 text-xs border border-[#E2E8F0] rounded hover:bg-slate-50 transition cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={isLoggingManual}
                          className="px-2.5 py-1 text-xs bg-[#2563EB] text-white rounded hover:bg-blue-700 transition cursor-pointer disabled:opacity-50"
                        >
                          {isLoggingManual ? "Logging..." : "Log Time"}
                        </button>
                      </div>
                    </div>
                  </form>
                )}

                <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
                  {isManualLoading ? (
                    <div className="text-xs text-[#94A3B8]">Loading manual logs...</div>
                  ) : manualEntries.length === 0 ? (
                    <div className="text-xs text-[#94A3B8] italic">No manual entries logged.</div>
                  ) : (
                    manualEntries.map((entry) => {
                      const hrs = Math.floor(entry.total_seconds / 3600);
                      const mins = Math.floor((entry.total_seconds % 3600) / 60);
                      return (
                        <div key={entry.id} className="flex items-center justify-between p-2 bg-[#F8FAFC] border border-[#F1F5F9] rounded text-xs text-[#64748B]">
                          <div>
                            <span className="font-semibold text-[#0F172A]">{entry.work_date}</span>
                            <span className="mx-2">•</span>
                            <span className="font-medium text-[#0F172A]">{hrs}h {mins}m</span>
                            {entry.is_billable && (
                              <span className="ml-2 px-1 py-0.5 bg-green-50 text-green-600 rounded text-[10px] font-semibold border border-green-200">
                                Billable
                              </span>
                            )}
                          </div>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            entry.approval_status === "approved"
                              ? "bg-green-50 text-green-700 border border-green-200"
                              : entry.approval_status === "rejected"
                              ? "bg-red-50 text-red-700 border border-red-200"
                              : "bg-amber-50 text-amber-700 border border-amber-200"
                          }`}>
                            {entry.approval_status}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-[#F1F5F9] text-xs text-[#94A3B8]">
                <div>
                  Created: {formatDateTime(selectedTask.created_at)}
                </div>
                <div>
                  Last Updated: {formatDateTime(selectedTask.updated_at)}
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[#F1F5F9] flex items-center justify-end">
              <button
                type="button"
                onClick={() => setSelectedTask(null)}
                className="px-4 py-2 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-md text-sm font-semibold text-[#64748B] transition cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal - Archive Task */}
      {taskToArchive && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="relative bg-white rounded-xl shadow-xl border border-[#E2E8F0] max-w-sm w-full overflow-hidden p-6 space-y-4 text-center">
            <div className="w-12 h-12 bg-red-50 text-red-600 rounded-full flex items-center justify-center mx-auto mb-2">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            
            <h3 className="text-lg font-bold text-[#0F172A]">Archive Task?</h3>
            <p className="text-sm text-[#64748B]">
              Are you sure you want to archive <strong>{taskToArchive.task_name}</strong>? This task will be removed from your active board.
            </p>

            {archiveError && (
              <div className="p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-600">
                {archiveError}
              </div>
            )}

            <div className="pt-4 flex items-center justify-center gap-3">
              <button
                type="button"
                disabled={isArchiving}
                onClick={() => setTaskToArchive(null)}
                className="px-4 py-2 border border-[#E2E8F0] rounded-md text-xs font-semibold text-[#64748B] hover:bg-slate-50 transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isArchiving}
                onClick={handleArchiveConfirm}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-xs font-semibold text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-600 transition cursor-pointer flex items-center gap-2"
              >
                {isArchiving ? "Archiving..." : "Archive Task"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default ProjectList;
