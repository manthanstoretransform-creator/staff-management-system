import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { MemberShell } from "./MemberShell";
import { Avatar, Card, EmptyState, ErrorNote, ProgressBar, Spinner, StatusPill } from "./MemberUi";
import { useGetAllProjectsQuery } from "../../store/api/projectsApi";
import { useGetTeamProjectByIdQuery } from "../../store/api/teamsApi";
import { useAuth } from "../auth/authContext";
import { series } from "../dashboard/v2/theme";
import { formatISTDate } from "../../utils/duration";

/**
 * The member's team.
 *
 * Where the admin Teams screen starts from the org's leaders, this one starts
 * from the member: the projects they belong to, and for each the leader they
 * report to on it plus the colleagues on the same project. There is no route
 * from here to a project the member is not on — `/teams/projects/{id}` 404s
 * for a non-member, and `/projects` never lists one in the first place.
 */

interface TeamMemberCard {
  id: number;
  name: string;
  designation: string | null;
  initials: string;
  role: string;
  total_tasks: number;
  completed_tasks: number;
  task_progress: { completed: number; total: number; percentage: number };
  tasks: { id: number; name: string; status: { id: number; name: string; color: string } | null }[];
}

const ProjectPicker: React.FC = () => {
  const navigate = useNavigate();
  const { data: projects = [], isLoading, isError } = useGetAllProjectsQuery();

  if (isLoading) return <Spinner label="Finding your teams…" />;
  if (isError) return <ErrorNote message="Your teams could not be loaded. Please try again." />;

  if (projects.length === 0) {
    return (
      <Card>
        <EmptyState
          message="You are not on any project teams yet."
          hint="Once a leader adds you to a project, that project's team appears here."
        />
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
      {projects.map((project, index) => (
        <button
          key={project.id}
          onClick={() => navigate(`/member/team/${project.id}`)}
          className="flex flex-col rounded-xl border border-[#E2E8F0] bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="min-w-0 flex-1 truncate text-[15px] font-bold text-[#0F172A]">
              {project.project_name}
            </h3>
            <StatusPill status={project.status} />
          </div>

          <div className="mt-4 flex items-center gap-3 rounded-lg bg-[#F8FAFC] p-3">
            <Avatar
              name={project.leader?.name || "?"}
              size={34}
              color={series[index % series.length]}
            />
            <div className="min-w-0">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#94A3B8]">Team leader</div>
              <div className="truncate text-[13px] font-bold text-[#0F172A]">
                {project.leader?.name || "Unassigned"}
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-[#F1F5F9] pt-4">
            <div className="flex items-center">
              {(project.employees || []).slice(0, 5).map((employee, i) => (
                <div key={employee.id} className={i === 0 ? "" : "-ml-2"}>
                  <Avatar name={employee.name} size={26} color={series[i % series.length]} ring />
                </div>
              ))}
            </div>
            <span className="text-[12px] font-bold text-[#64748B]">
              {project.employee_count ?? (project.employees || []).length} member
              {(project.employee_count ?? (project.employees || []).length) === 1 ? "" : "s"}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
};

const ProjectTeam: React.FC<{ projectId: number }> = ({ projectId }) => {
  const { currentUser } = useAuth();
  const { data: project, isLoading, isError } = useGetTeamProjectByIdQuery(projectId);

  if (isLoading) return <Spinner label="Loading this team…" />;
  if (isError || !project) {
    return (
      <ErrorNote message="This team could not be loaded. You may no longer be a member of this project." />
    );
  }

  const members = (project.members?.items ?? []) as TeamMemberCard[];
  const progress = project.task_progress;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card title="Team leader" className="lg:col-span-1">
          {project.leader ? (
            <div className="flex items-center gap-4">
              <Avatar name={project.leader.name} size={52} color={series[0]} />
              <div className="min-w-0">
                <div className="truncate text-[15px] font-bold text-[#0F172A]">{project.leader.name}</div>
                <div className="truncate text-[13px] text-[#64748B]">
                  {project.leader.designation || "Project leader"}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState message="This project has no leader assigned." />
          )}
        </Card>

        <Card title="Project" className="lg:col-span-2">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-[15px] font-bold text-[#0F172A]">{project.project_name}</span>
            <StatusPill status={project.status} />
            {project.deadline && (
              <span className="text-[12px] font-semibold text-[#64748B]">
                Due {formatISTDate(project.deadline)}
              </span>
            )}
          </div>
          <p className="mt-2 text-[13px] leading-5 text-[#64748B]">
            {project.description || "No description."}
          </p>
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-[#94A3B8]">
              <span>Task progress</span>
              <span className="text-[#0F172A]">
                {progress?.completed ?? 0}/{progress?.total ?? 0} ({progress?.percentage ?? 0}%)
              </span>
            </div>
            <ProgressBar value={progress?.percentage ?? 0} color={series[1]} />
            {project.unassigned_task_count > 0 && (
              <p className="mt-2 text-[12px] font-semibold text-amber-600">
                {project.unassigned_task_count} task
                {project.unassigned_task_count === 1 ? " is" : "s are"} still unassigned.
              </p>
            )}
          </div>
        </Card>
      </div>

      <Card title={`Team members (${members.length})`}>
        {members.length === 0 ? (
          <EmptyState message="No members are assigned to this project." />
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {members.map((member, index) => {
              const isMe = member.id === currentUser?.id;
              return (
                <div
                  key={member.id}
                  className={
                    "rounded-xl border p-4 transition " +
                    (isMe ? "border-[#2563EB] bg-[#2563EB]/[0.04]" : "border-[#E2E8F0] bg-white")
                  }
                >
                  <div className="flex items-center gap-3">
                    <Avatar name={member.name} size={40} color={series[index % series.length]} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[14px] font-bold text-[#0F172A]">{member.name}</span>
                        {isMe && (
                          <span className="shrink-0 rounded-full bg-[#2563EB] px-2 py-0.5 text-[10px] font-bold text-white">
                            You
                          </span>
                        )}
                      </div>
                      <div className="truncate text-[12px] text-[#64748B]">
                        {member.designation || member.role}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-[#94A3B8]">
                      <span>Tasks</span>
                      <span className="text-[#0F172A]">
                        {member.task_progress?.completed ?? 0}/{member.task_progress?.total ?? 0}
                      </span>
                    </div>
                    <ProgressBar
                      value={member.task_progress?.percentage ?? 0}
                      color={series[index % series.length]}
                    />
                  </div>

                  {member.tasks?.length ? (
                    <ul className="mt-4 space-y-1.5 border-t border-[#F1F5F9] pt-3">
                      {member.tasks.slice(0, 4).map((task) => (
                        <li key={task.id} className="flex items-center justify-between gap-2 text-[12px]">
                          <span className="min-w-0 flex-1 truncate text-[#64748B]">{task.name}</span>
                          <StatusPill status={task.status} />
                        </li>
                      ))}
                      {member.tasks.length > 4 && (
                        <li className="pt-0.5 text-[11px] font-semibold text-[#94A3B8]">
                          +{member.tasks.length - 4} more
                        </li>
                      )}
                    </ul>
                  ) : (
                    <p className="mt-4 border-t border-[#F1F5F9] pt-3 text-[12px] text-[#94A3B8]">
                      No tasks assigned on this project.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
};

export const MemberTeam: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const numericProjectId = projectId ? Number(projectId) : null;

  return (
    <MemberShell
      title={numericProjectId ? "Project Team" : "My Team"}
      subtitle={
        numericProjectId
          ? "Your leader and the colleagues you share this project with."
          : "Pick one of your projects to see its leader and members."
      }
      breadcrumb={
        numericProjectId ? (
          <button
            onClick={() => navigate("/member/team")}
            className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#64748B] transition hover:text-[#2563EB]"
          >
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M15 19l-7-7 7-7" />
            </svg>
            My Team
          </button>
        ) : undefined
      }
    >
      <div className="w-full pb-20">
        {numericProjectId && Number.isFinite(numericProjectId) ? (
          <ProjectTeam projectId={numericProjectId} />
        ) : (
          <ProjectPicker />
        )}
      </div>
    </MemberShell>
  );
};
