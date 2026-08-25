/**
 * Shared org data for the V2 admin pages (Project Management + Teams).
 *
 * Kept in one module so a leader / employee / project seed added here shows up
 * on every page at once. Swap `generateMockProjects` for the API call when the
 * projects endpoint lands — the shapes below are what the components expect.
 */

export type ProjectStatus = 'Active' | 'Pending' | 'To Do' | 'Completed';
/** How a billable project is timed: a capped budget of hours, or open ended. */
export type BillingMode = 'Fixed Hours' | 'Free Time';
export type TaskStatus = 'To Do' | 'In Progress' | 'Completed';

export type Leader = { id: string; name: string; title: string; accent: string };
export type Employee = { id: string; name: string; leaderId: string; title: string };

export type Task = {
  id: string;
  name: string;
  assigneeId: string;
  status: TaskStatus;
};

export type Project = {
  id: string;
  name: string;
  leaderId: string;
  deadline: string;
  employees: string[];
  status: ProjectStatus;
  tasks: Task[];
  description: string;
  /** Whether the project is billed to the client at all. */
  billable: boolean;
  /** Only meaningful when billable — undefined on non-billable projects. */
  billingMode?: BillingMode;
  /** Hour budget for the project. Only set when billingMode is 'Fixed Hours'. */
  billingHours?: number;
};

/**
 * Accents come from the validated categorical slots in the V2 theme. Colour
 * follows the leader everywhere — the same hue identifies them on the team
 * card, the project list and the member breakdown.
 */
export const LEADERS: Leader[] = [
  { id: 'l1', name: 'Alice Cooper', title: 'Engineering Lead', accent: '#2563EB' },
  { id: 'l2', name: 'Bob Smith', title: 'Delivery Lead', accent: '#0D9488' },
  { id: 'l3', name: 'Charlie Davis', title: 'Product Lead', accent: '#7C3AED' },
];

export const EMPLOYEES: Employee[] = [
  { id: 'e1', name: 'David Evans', leaderId: 'l1', title: 'Frontend Engineer' },
  { id: 'e2', name: 'Eve Foster', leaderId: 'l1', title: 'Backend Engineer' },
  { id: 'e3', name: 'Frank Green', leaderId: 'l1', title: 'QA Analyst' },
  { id: 'e4', name: 'Grace Hall', leaderId: 'l2', title: 'Product Designer' },
  { id: 'e5', name: 'Henry Ives', leaderId: 'l2', title: 'DevOps Engineer' },
  { id: 'e6', name: 'Ivy Jones', leaderId: 'l2', title: 'Data Analyst' },
  { id: 'e7', name: 'Jack King', leaderId: 'l3', title: 'Mobile Engineer' },
  { id: 'e8', name: 'Karen Lee', leaderId: 'l3', title: 'UX Researcher' },
];

export const STATUSES: ProjectStatus[] = ['Active', 'Pending', 'To Do', 'Completed'];

/** Semantic status palette — one hue per state, reused on every V2 surface. */
export const STATUS_COLORS: Record<ProjectStatus, string> = {
  Active: '#2563EB',
  Pending: '#F59E0B',
  'To Do': '#64748B',
  Completed: '#10B981',
};

export const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  'To Do': '#94A3B8',
  'In Progress': '#F59E0B',
  Completed: '#10B981',
};

const TASK_NAMES = [
  'Design Phase',
  'API Integration',
  'Unit Testing',
  'Client Review',
  'Deployment Prep',
];

export const generateMockProjects = (): Project[] => {
  const projects: Project[] = [];
  for (let i = 1; i <= 35; i++) {
    const leaderId = `l${(i % 3) + 1}`;
    const leaderEmps = EMPLOYEES.filter(e => e.leaderId === leaderId).map(e => e.id);
    const assigned = leaderEmps.slice(0, (i % 3) + 1);
    const randomStatus = STATUSES[i % 4];
    // Every third project is non-billable; the rest alternate between a
    // capped hour budget and open-ended (free) time.
    const billable = i % 3 !== 0;
    const billingMode: BillingMode | undefined = billable
      ? (i % 2 === 0 ? 'Fixed Hours' : 'Free Time')
      : undefined;

    // Two tasks per assignee so the member breakdown has something to show.
    const mockTasks: Task[] = assigned.flatMap((empId, tIndex) =>
      [0, 1].map(k => {
        const seed = i + tIndex * 2 + k;
        return {
          id: `t${i}_${tIndex}_${k}`,
          name: `${TASK_NAMES[seed % TASK_NAMES.length]} ${tIndex + 1}`,
          assigneeId: empId,
          status: (['To Do', 'In Progress', 'Completed'] as TaskStatus[])[seed % 3],
        };
      })
    );

    projects.push({
      id: `p${i}`,
      name: `Project Alpha ${i}`,
      description: `This is a detailed description for Project Alpha ${i}. It includes all the necessary requirements and objectives that need to be met by the assigned team before the deadline.`,
      leaderId,
      deadline: `2026-12-${String((i % 28) + 1).padStart(2, '0')}`,
      employees: assigned,
      status: randomStatus,
      tasks: mockTasks,
      billable,
      billingMode,
      billingHours: billingMode === 'Fixed Hours' ? 40 + (i % 6) * 20 : undefined,
    });
  }
  return projects.reverse();
};

export const INITIAL_PROJECTS = generateMockProjects();

/* ------------------------------------------------------------------ */
/* Lookup helpers                                                      */
/* ------------------------------------------------------------------ */

export const leaderById = (id: string) => LEADERS.find(l => l.id === id);
export const employeeById = (id: string) => EMPLOYEES.find(e => e.id === id);

export const getInitials = (name: string) => {
  if (!name) return '??';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
};

export const formatDeadline = (dateStr: string) => {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const day = String(date.getDate()).padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short' });
  return `${day} ${month} ${date.getFullYear()}`;
};
