import React, { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { V2Shell } from '../dashboard/v2/V2Shell';
import { brandGradient } from '../dashboard/v2/theme';
import {
  EMPLOYEES,
  INITIAL_PROJECTS,
  LEADERS,
  STATUSES,
  STATUS_COLORS,
  TASK_STATUS_COLORS,
  employeeById,
  formatDeadline,
  getInitials,
  leaderById,
  type Project,
  type ProjectStatus,
} from './teamData';

/* ------------------------------------------------------------------ */
/* Shared bits                                                         */
/* ------------------------------------------------------------------ */

/** Initials avatar tinted with the entity's own accent. */
const Avatar: React.FC<{ name: string; color: string; size?: number; ring?: boolean }> = ({
  name,
  color,
  size = 40,
  ring = false,
}) => (
  <div
    className={'flex shrink-0 items-center justify-center rounded-full font-bold ' + (ring ? 'ring-2 ring-white' : '')}
    style={{
      width: size,
      height: size,
      background: `${color}1A`,
      color,
      fontSize: size * 0.36,
      letterSpacing: '0.02em',
    }}
    title={name}
  >
    {getInitials(name)}
  </div>
);

const AvatarStack: React.FC<{ ids: string[]; max?: number }> = ({ ids, max = 4 }) => {
  const shown = ids.slice(0, max);
  const rest = ids.length - shown.length;
  return (
    <div className="flex items-center">
      {shown.map((id, i) => {
        const emp = employeeById(id);
        const accent = leaderById(emp?.leaderId || '')?.accent || '#64748B';
        return (
          <div key={id} style={{ marginLeft: i === 0 ? 0 : -10, zIndex: shown.length - i }}>
            <Avatar name={emp?.name || '?'} color={accent} size={30} ring />
          </div>
        );
      })}
      {rest > 0 && (
        <div
          className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500 ring-2 ring-white"
          style={{ marginLeft: -10 }}
        >
          +{rest}
        </div>
      )}
    </div>
  );
};

const StatusPill: React.FC<{ status: ProjectStatus }> = ({ status }) => {
  const color = STATUS_COLORS[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold tracking-wide"
      style={{ background: `${color}14`, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {status}
    </span>
  );
};

const ProgressBar: React.FC<{ value: number; color: string }> = ({ value, color }) => (
  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
    <div
      className="h-full rounded-full transition-all duration-500"
      style={{ width: `${Math.round(value * 100)}%`, background: color }}
    />
  </div>
);

const StatTile: React.FC<{ label: string; value: React.ReactNode; color: string; icon: string }> = ({
  label,
  value,
  color,
  icon,
}) => (
  <div className="flex items-center gap-3.5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg"
      style={{ background: `${color}14`, color }}
    >
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={icon} />
      </svg>
    </div>
    <div className="min-w-0">
      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
      <div className="text-xl font-bold leading-tight text-[#0F172A]">{value}</div>
    </div>
  </div>
);

const SearchBox: React.FC<{ value: string; onChange: (v: string) => void; placeholder: string }> = ({
  value,
  onChange,
  placeholder,
}) => (
  <div className="flex flex-1 items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition focus-within:border-[#38BDF8]">
    <svg className="h-4.5 w-4.5 shrink-0 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
    <input
      type="text"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
    />
  </div>
);

const EmptyState: React.FC<{ message: string }> = ({ message }) => (
  <div className="rounded-xl border border-dashed border-slate-300 bg-white p-14 text-center">
    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
      <svg className="h-6 w-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>
    <div className="text-sm font-semibold text-slate-600">{message}</div>
  </div>
);

const Chevron: React.FC<{ color: string }> = ({ color }) => (
  <svg className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" style={{ color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
  </svg>
);

const Crumb: React.FC<{ items: { label: string; onClick?: () => void }[] }> = ({ items }) => (
  <div className="mb-0.5 flex items-center gap-1.5 text-[11px] font-semibold">
    {items.map((item, i) => (
      <React.Fragment key={item.label + i}>
        {i > 0 && <span className="text-slate-300">/</span>}
        {item.onClick ? (
          <button onClick={item.onClick} className="text-[#2563EB] transition hover:underline">
            {item.label}
          </button>
        ) : (
          <span className="text-slate-400">{item.label}</span>
        )}
      </React.Fragment>
    ))}
  </div>
);

const doneRatio = (project: Project) => {
  if (!project.tasks.length) return 0;
  return project.tasks.filter(t => t.status === 'Completed').length / project.tasks.length;
};

/* ------------------------------------------------------------------ */
/* Level 1 — Leaders                                                   */
/* ------------------------------------------------------------------ */

const LeadersView: React.FC<{ projects: Project[]; onOpen: (leaderId: string) => void }> = ({ projects, onOpen }) => {
  const [search, setSearch] = useState('');

  const rows = useMemo(
    () =>
      LEADERS.map(leader => {
        const own = projects.filter(p => p.leaderId === leader.id);
        const team = EMPLOYEES.filter(e => e.leaderId === leader.id);
        return {
          leader,
          projects: own,
          team,
          active: own.filter(p => p.status === 'Active').length,
          completed: own.filter(p => p.status === 'Completed').length,
        };
      }),
    [projects]
  );

  const filtered = rows.filter(r => r.leader.name.toLowerCase().includes(search.trim().toLowerCase()));

  const totalActive = rows.reduce((sum, r) => sum + r.active, 0);

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl p-7 text-white shadow-lg" style={{ background: brandGradient }}>
        <div className="absolute -right-10 -top-16 h-52 w-52 rounded-full bg-white/10" />
        <div className="absolute -bottom-20 right-24 h-40 w-40 rounded-full bg-white/5" />
        <div className="relative">
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/70">Organisation</div>
          <h2 className="mt-1.5 text-2xl font-bold tracking-tight">Team Structure</h2>
          <p className="mt-1.5 max-w-xl text-sm text-white/80">
            Pick a leader to see the projects they run, then open a project to see who is working on it.
          </p>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Team Leaders"
          value={LEADERS.length}
          color="#2563EB"
          icon="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
        />
        <StatTile
          label="Employees"
          value={EMPLOYEES.length}
          color="#0D9488"
          icon="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
        />
        <StatTile
          label="Total Projects"
          value={projects.length}
          color="#7C3AED"
          icon="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
        />
        <StatTile
          label="Active Now"
          value={totalActive}
          color="#F59E0B"
          icon="M13 10V3L4 14h7v7l9-11h-7z"
        />
      </div>

      <SearchBox value={search} onChange={setSearch} placeholder="Search leaders by name..." />

      {/* Leader cards */}
      {filtered.length === 0 ? (
        <EmptyState message="No leader matches that search." />
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map(({ leader, projects: own, team, active, completed }) => (
            <button
              key={leader.id}
              onClick={() => onOpen(leader.id)}
              className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white text-left shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-xl"
              style={{ ['--accent' as any]: leader.accent }}
            >
              <div className="h-1.5 w-full" style={{ background: leader.accent }} />

              <div className="p-5">
                <div className="flex items-center gap-3.5">
                  <Avatar name={leader.name} color={leader.accent} size={52} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-base font-bold text-[#0F172A]">{leader.name}</div>
                    <div className="truncate text-xs font-medium" style={{ color: leader.accent }}>
                      {leader.title}
                    </div>
                  </div>
                  <Chevron color={leader.accent} />
                </div>

                <div className="mt-5 grid grid-cols-3 divide-x divide-slate-100 rounded-xl bg-slate-50 py-3">
                  {[
                    { label: 'Projects', value: own.length },
                    { label: 'Members', value: team.length },
                    { label: 'Active', value: active },
                  ].map(stat => (
                    <div key={stat.label} className="px-2 text-center">
                      <div className="text-lg font-bold leading-tight text-[#0F172A]">{stat.value}</div>
                      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{stat.label}</div>
                    </div>
                  ))}
                </div>

                <div className="mt-4">
                  <div className="mb-1.5 flex items-center justify-between text-[11px] font-semibold">
                    <span className="text-slate-400">Completion</span>
                    <span className="text-slate-600">
                      {completed} / {own.length} done
                    </span>
                  </div>
                  <ProgressBar value={own.length ? completed / own.length : 0} color={leader.accent} />
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4">
                  <AvatarStack ids={team.map(t => t.id)} />
                  <span className="text-xs font-bold" style={{ color: leader.accent }}>
                    View team
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Level 2 — Projects under a leader                                   */
/* ------------------------------------------------------------------ */

const LeaderProjectsView: React.FC<{
  leaderId: string;
  projects: Project[];
  onOpen: (projectId: string) => void;
  onBack: () => void;
}> = ({ leaderId, projects, onOpen, onBack }) => {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<ProjectStatus | 'All'>('All');

  const leader = leaderById(leaderId);
  const own = useMemo(() => projects.filter(p => p.leaderId === leaderId), [projects, leaderId]);
  const team = EMPLOYEES.filter(e => e.leaderId === leaderId);

  if (!leader) return <EmptyState message="That leader no longer exists." />;

  const counts: Record<string, number> = { All: own.length };
  STATUSES.forEach(s => (counts[s] = own.filter(p => p.status === s).length));

  const filtered = own.filter(
    p =>
      p.name.toLowerCase().includes(search.trim().toLowerCase()) && (status === 'All' || p.status === status)
  );

  return (
    <div className="space-y-6">
      {/* Leader banner */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="h-1.5 w-full" style={{ background: leader.accent }} />
        <div className="flex flex-col gap-4 p-6 md:flex-row md:items-center">
          <Avatar name={leader.name} color={leader.accent} size={58} />
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-bold tracking-tight text-[#0F172A]">{leader.name}</h2>
            <div className="text-sm font-medium" style={{ color: leader.accent }}>
              {leader.title}
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div className="text-xl font-bold text-[#0F172A]">{own.length}</div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Projects</div>
            </div>
            <div className="h-9 w-px bg-slate-200" />
            <div>
              <AvatarStack ids={team.map(t => t.id)} max={5} />
              <div className="mt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                {team.length} Members
              </div>
            </div>
            <button
              onClick={onBack}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-600 shadow-sm transition hover:bg-slate-50"
            >
              ← All Teams
            </button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <SearchBox value={search} onChange={setSearch} placeholder="Search projects by name..." />
        <div className="flex flex-wrap items-center gap-2">
          {(['All', ...STATUSES] as const).map(s => {
            const active = status === s;
            const color = s === 'All' ? leader.accent : STATUS_COLORS[s as ProjectStatus];
            return (
              <button
                key={s}
                onClick={() => setStatus(s as ProjectStatus | 'All')}
                className={
                  'rounded-lg border px-3.5 py-2 text-xs font-bold transition ' +
                  (active ? 'text-white shadow-sm' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50')
                }
                style={active ? { background: color, borderColor: color } : undefined}
              >
                {s} <span className={active ? 'text-white/70' : 'text-slate-400'}>({counts[s] ?? 0})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Project cards */}
      {filtered.length === 0 ? (
        <EmptyState message="No project matches these filters." />
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map(project => {
            const ratio = doneRatio(project);
            const done = project.tasks.filter(t => t.status === 'Completed').length;
            return (
              <button
                key={project.id}
                onClick={() => onOpen(project.id)}
                className="group rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-xl"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-[15px] font-bold text-[#0F172A]">{project.name}</div>
                    <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {formatDeadline(project.deadline)}
                    </div>
                  </div>
                  <StatusPill status={project.status} />
                </div>

                <p className="mt-3 line-clamp-2 text-xs leading-relaxed text-slate-500">{project.description}</p>

                <div className="mt-4">
                  <div className="mb-1.5 flex items-center justify-between text-[11px] font-semibold">
                    <span className="text-slate-400">Task progress</span>
                    <span className="text-slate-600">
                      {done} / {project.tasks.length}
                    </span>
                  </div>
                  <ProgressBar value={ratio} color={STATUS_COLORS[project.status]} />
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4">
                  <div className="flex items-center gap-2.5">
                    <AvatarStack ids={project.employees} />
                    <span className="text-xs font-semibold text-slate-500">
                      {project.employees.length} working
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-xs font-bold" style={{ color: leader.accent }}>
                    Members <Chevron color={leader.accent} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Level 3 — Employees on a project                                    */
/* ------------------------------------------------------------------ */

const ProjectMembersView: React.FC<{
  project: Project;
  onBack: () => void;
}> = ({ project, onBack }) => {
  const leader = leaderById(project.leaderId);
  const accent = leader?.accent || '#2563EB';
  const done = project.tasks.filter(t => t.status === 'Completed').length;

  return (
    <div className="space-y-6">
      {/* Project banner */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="h-1.5 w-full" style={{ background: STATUS_COLORS[project.status] }} />
        <div className="p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold tracking-tight text-[#0F172A]">{project.name}</h2>
                <StatusPill status={project.status} />
              </div>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">{project.description}</p>
            </div>
            <button
              onClick={onBack}
              className="shrink-0 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-600 shadow-sm transition hover:bg-slate-50"
            >
              ← {leader?.name.split(' ')[0]}'s Projects
            </button>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-100 pt-5 lg:grid-cols-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Team Leader</div>
              <div className="mt-1.5 flex items-center gap-2">
                <Avatar name={leader?.name || '?'} color={accent} size={26} />
                <span className="text-sm font-semibold text-slate-700">{leader?.name}</span>
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Deadline</div>
              <div className="mt-1.5 text-sm font-semibold text-slate-700">{formatDeadline(project.deadline)}</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Members</div>
              <div className="mt-1.5 text-sm font-semibold text-slate-700">{project.employees.length} assigned</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Tasks Completed</div>
              <div className="mt-1.5 text-sm font-semibold text-slate-700">
                {done} of {project.tasks.length}
              </div>
              <div className="mt-1.5">
                <ProgressBar value={doneRatio(project)} color={STATUS_COLORS[project.status]} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Member cards */}
      {project.employees.length === 0 ? (
        <EmptyState message="No employee is assigned to this project yet." />
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {project.employees.map(empId => {
            const emp = employeeById(empId);
            const tasks = project.tasks.filter(t => t.assigneeId === empId);
            const empDone = tasks.filter(t => t.status === 'Completed').length;
            return (
              <div
                key={empId}
                className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:shadow-lg"
              >
                <div className="flex items-center gap-3.5">
                  <Avatar name={emp?.name || '?'} color={accent} size={46} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[15px] font-bold text-[#0F172A]">{emp?.name}</div>
                    <div className="truncate text-xs font-medium text-slate-500">{emp?.title}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-base font-bold text-[#0F172A]">{tasks.length}</div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Tasks</div>
                  </div>
                </div>

                <div className="mt-4">
                  <div className="mb-1.5 flex items-center justify-between text-[11px] font-semibold">
                    <span className="text-slate-400">Their progress</span>
                    <span className="text-slate-600">
                      {empDone} / {tasks.length} done
                    </span>
                  </div>
                  <ProgressBar value={tasks.length ? empDone / tasks.length : 0} color={accent} />
                </div>

                <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Tasks in this project
                  </div>
                  {tasks.length === 0 ? (
                    <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-xs italic text-slate-400">
                      No task assigned yet.
                    </div>
                  ) : (
                    tasks.map(task => {
                      const color = TASK_STATUS_COLORS[task.status];
                      return (
                        <div
                          key={task.id}
                          className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2.5"
                        >
                          <div className="flex min-w-0 items-center gap-2.5">
                            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
                            <span className="truncate text-xs font-semibold text-slate-700">{task.name}</span>
                          </div>
                          <span
                            className="shrink-0 rounded-md px-2 py-0.5 text-[10px] font-bold"
                            style={{ background: `${color}14`, color }}
                          >
                            {task.status}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export const AdminTeams: React.FC = () => {
  const navigate = useNavigate();
  const { leaderId, projectId } = useParams<{ leaderId: string; projectId: string }>();
  const [projects] = useState<Project[]>(INITIAL_PROJECTS);

  const leader = leaderId ? leaderById(leaderId) : undefined;
  const project = projectId ? projects.find(p => p.id === projectId) : undefined;

  const goRoot = () => navigate('/admin/teams');
  const goLeader = (id: string) => navigate(`/admin/teams/${id}`);

  let title = 'V2 Teams';
  let subtitle = 'Leaders, the projects they run, and who works on them.';
  let breadcrumb: React.ReactNode = null;
  let body: React.ReactNode;

  if (project && leader) {
    title = project.name;
    subtitle = `${project.employees.length} member${project.employees.length === 1 ? '' : 's'} working under ${leader.name}`;
    breadcrumb = (
      <Crumb
        items={[
          { label: 'Teams', onClick: goRoot },
          { label: leader.name, onClick: () => goLeader(leader.id) },
          { label: project.name },
        ]}
      />
    );
    body = <ProjectMembersView project={project} onBack={() => goLeader(leader.id)} />;
  } else if (leader) {
    const count = projects.filter(p => p.leaderId === leader.id).length;
    title = `${leader.name}'s Team`;
    subtitle = `${count} project${count === 1 ? '' : 's'} — open one to see its members.`;
    breadcrumb = <Crumb items={[{ label: 'Teams', onClick: goRoot }, { label: leader.name }]} />;
    body = (
      <LeaderProjectsView
        leaderId={leader.id}
        projects={projects}
        onOpen={pid => navigate(`/admin/teams/${leader.id}/${pid}`)}
        onBack={goRoot}
      />
    );
  } else if (leaderId || projectId) {
    body = <EmptyState message="We couldn't find that team or project." />;
  } else {
    body = <LeadersView projects={projects} onOpen={goLeader} />;
  }

  return (
    <V2Shell title={title} subtitle={subtitle} breadcrumb={breadcrumb}>
      <div className="mx-auto max-w-7xl pb-20">{body}</div>
    </V2Shell>
  );
};
