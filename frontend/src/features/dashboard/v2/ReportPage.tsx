import React, { useMemo, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { V2Shell } from "./V2Shell";
import { Legend, RankedBars } from "./charts";
import {
  DateRangeFilter,
  DEFAULT_RANGE,
  exportToCsv,
  MemberMultiSelect,
  ProjectMultiSelect,
  rangeForMonth,
} from "./filters";
import type { DateRange } from "./filters";
import { series } from "./theme";
import { monthByKey } from "./mockData";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { useGetGroupedReportQuery, useGetDetailedLogsQuery } from "../../../store/api/reportsApi";
import { formatHMS, formatHoursAsHMS } from "../../../utils/duration";
import { useGetMembersQuery } from "../../../store/api/membersApi";
import { useGetAllProjectsQuery } from "../../../store/api/projectsApi";

type ReportId = "projects" | "members" | "tasks" | "apps";
type SortKey = "date" | "member" | "project" | "task" | "hours" | "activity";

const REPORTS: Record<
  ReportId,
  { title: string; subtitle: string; dimension: string; dimensionLabel: string; color: string }
> = {
  projects: {
    title: "Project-Wise Activity Report",
    subtitle: "Every project in the selected period, not just the dashboard top 10",
    dimension: "project",
    dimensionLabel: "Project",
    color: series[0],
  },
  members: {
    title: "Member-Wise Activity Report",
    subtitle: "Every member in the selected period, not just the dashboard top 10",
    dimension: "member",
    dimensionLabel: "Member",
    color: series[1],
  },
  tasks: {
    title: "Top Tasks Report",
    subtitle: "Every task in the selected period, not just the dashboard top 10",
    dimension: "task",
    dimensionLabel: "Task",
    color: series[2],
  },
  apps: {
    title: "Apps & URLs Usage Report",
    subtitle: "Every application and website in the selected period",
    dimension: "app",
    dimensionLabel: "App",
    color: series[3],
  },
};

const PAGE_SIZES = [25, 50, 100];

const SummaryTile: React.FC<{ label: string; value: string; caption: string; color: string }> = ({
  label,
  value,
  caption,
  color,
}) => (
  <div className="rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-sm">
    <div className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      <span className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">{label}</span>
    </div>
    <div className="mt-3 text-[28px] font-extrabold leading-none tracking-tight text-[#0F172A]">{value}</div>
    <div className="mt-1.5 text-[11px] text-[#94A3B8]">{caption}</div>
  </div>
);

const SortHeader: React.FC<{
  label: string;
  sortKey: SortKey;
  active: SortKey;
  desc: boolean;
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
}> = ({ label, sortKey, active, desc, onSort, align = "left" }) => (
  <th className={"px-5 py-3 " + (align === "right" ? "text-right" : "text-left")}>
    <button
      onClick={() => onSort(sortKey)}
      className={
        "inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider transition " +
        (active === sortKey ? "text-[#2563EB]" : "text-[#64748B] hover:text-[#0F172A]")
      }
    >
      {label}
      <svg
        className={"h-3 w-3 transition " + (active === sortKey && !desc ? "rotate-180" : "")}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        style={{ opacity: active === sortKey ? 1 : 0.35 }}
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
  </th>
);

export const ReportPage: React.FC = () => {
  const { reportId } = useParams<{ reportId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const monthParam = searchParams.get("month");

  const [range, setRange] = useState<DateRange>(() =>
    monthParam ? rangeForMonth(monthParam) : DEFAULT_RANGE
  );
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [usageTab, setUsageTab] = useState<"app" | "url">("app");
  const [groupSort, setGroupSort] = useState<"hours" | "activity" | "name">("hours");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDesc, setSortDesc] = useState(true);
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(1);

  // The filter dropdowns list everything, so ask for the full page size the
  // backend allows rather than its default 20.
  const { data: membersResponse } = useGetMembersQuery({ limit: 100 });
  const membersData = membersResponse?.items ?? [];

  const { data: projectsData } = useGetAllProjectsQuery();
  const allProjects = projectsData ?? [];

  const config = REPORTS[reportId as ReportId];
  const dimensionLabel = config ? (config.dimension === "app" ? (usageTab === "app" ? "App" : "URL") : config.dimensionLabel) : "Project";

  const { data: groupedData } = useGetGroupedReportQuery(
    {
      dimension: reportId as string,
      from: range.from,
      to: range.to,
      member_id: selectedMembers.length ? selectedMembers.map(Number) : undefined,
      project_id: selectedProjects.length ? selectedProjects.map(Number) : undefined,
      usage_type: reportId === "apps" ? usageTab : undefined,
    },
    { skip: !config }
  );

  const { data: detailedData } = useGetDetailedLogsQuery(
    {
      dimension: reportId as any,
      from: range.from,
      to: range.to,
      member_id: selectedMembers.length ? selectedMembers.map(Number) : undefined,
      project_id: selectedProjects.length ? selectedProjects.map(Number) : undefined,
      usage_type: reportId === "apps" ? usageTab : undefined,
      search: debouncedSearch,
      sort_by: sortKey,
      sort_desc: sortDesc,
      page,
      limit: pageSize,
    },
    { skip: !config }
  );

  const finalGrouped = useMemo(() => {
    if (!groupedData) return [];
    const list = (groupedData.grouped_data || []).map((item: any) => ({
      id: String(item.id),
      name: item.name,
      // `value` stays numeric hours: it drives the bar geometry and sorting.
      // The label the user reads is formatted from exact seconds.
      value: item.tracked_hours || 0,
      seconds: item.tracked_seconds || 0,
      secondary: item.activity_percentage || 0,
      meta: item.meta_label,
    }));
    
    if (groupSort === "name") return list.sort((a: any, b: any) => a.name.localeCompare(b.name));
    if (groupSort === "activity") return list.sort((a: any, b: any) => (b.secondary ?? 0) - (a.secondary ?? 0));
    return list.sort((a: any, b: any) => b.value - a.value);
  }, [groupedData, groupSort]);

  const summary = groupedData?.summary;
  const totalTrackedSeconds = summary?.total_tracked_seconds || 0;
  const avgActivity = summary?.average_activity_percentage || 0;
  const uniqueMembers = summary?.total_members || 0;
  const totalEntries = summary?.total_entries || 0;
  const totalGrouped = finalGrouped.length;

  const pageRows = (detailedData?.items || []).map((r: any) => ({
    id: r.id,
    date: r.date,
    member: r.member_name,
    memberId: String(r.member_id),
    role: r.role,
    project: r.project_name || "-",
    task: r.task_name || "-",
    app: r.app || "-",
    url: r.url || "-",
    hours: r.tracked_hours || 0,
    seconds: r.tracked_seconds || 0,
    activity: Number(r.activity_percentage) || 0,
  })) || [];

  const totalRows = detailedData?.pagination?.total || 0;
  const totalPages = detailedData?.pagination?.total_pages || 1;
  const safePage = detailedData?.pagination?.page || 1;

  if (!config) return <Navigate to="/dashboard-v2" replace />;

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(key === "hours" || key === "activity" || key === "date");
    }
    setPage(1);
  };

  const resetFilters = () => {
    setRange(monthParam ? rangeForMonth(monthParam) : DEFAULT_RANGE);
    setSelectedMembers([]);
    setSelectedProjects([]);
    setSearch("");
    setPage(1);
  };

  const handleExport = () => {
    exportToCsv(
      `${reportId}-report-${range.from}-to-${range.to}-page${safePage}.csv`,
      ["Date", "Member", "Role", "Project", "Task", "App", "URL", "Tracked time", "Activity %"],
      pageRows.map((r: any) => [
        r.date,
        r.member,
        r.role,
        r.project,
        r.task,
        r.app,
        r.url,
        formatHMS(r.seconds),
        r.activity,
      ])
    );
  };

  const handleExportSummary = () => {
    exportToCsv(
      `${reportId}-summary-${range.from}-to-${range.to}.csv`,
      [dimensionLabel, "Tracked time", "Avg Activity %", "Breakdown"],
      finalGrouped.map((g: any) => [g.name, formatHMS(g.seconds), g.secondary ?? 0, g.meta])
    );
  };

  return (
    <V2Shell
      title={config.title}
      subtitle={config.subtitle}
      breadcrumb={
        <button
          onClick={() => navigate("/dashboard-v2")}
          className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#64748B] transition hover:text-[#2563EB]"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M15 19l-7-7 7-7" />
          </svg>
          V2 Dashboard
          {monthParam && <span className="normal-case text-[#94A3B8]">· {monthByKey(monthParam).label}</span>}
        </button>
      }
      actions={
        <>
          <div className="hidden items-center rounded-lg border border-[#E2E8F0] bg-white p-0.5 lg:flex">
            {(Object.keys(REPORTS) as ReportId[]).map((id) => (
              <button
                key={id}
                onClick={() => navigate(`/dashboard-v2/reports/${id}${monthParam ? `?month=${monthParam}` : ""}`)}
                className={
                  "rounded-[6px] px-3 py-1.5 text-xs font-bold capitalize transition " +
                  (id === reportId ? "bg-[#2563EB] text-white shadow-sm" : "text-[#64748B] hover:text-[#0F172A]")
                }
              >
                {id}
              </button>
            ))}
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 rounded-lg bg-[#0F172A] px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#1E293B]"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
                d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"
              />
            </svg>
            Export CSV
          </button>
        </>
      }
    >
      <div className="mx-auto max-w-[1400px] space-y-6">
        {/* Filters */}
        <div className="space-y-3 rounded-2xl border border-[#E2E8F0] bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <DateRangeFilter value={range} onChange={(r: any) => { setRange(r); setPage(1); }} />
            <div className="flex flex-wrap items-center gap-2">
              <MemberMultiSelect
                members={membersData}
                selected={selectedMembers}
                onChange={(ids: any) => { setSelectedMembers(ids); setPage(1); }}
              />
              <ProjectMultiSelect
                projects={allProjects}
                selected={selectedProjects}
                onChange={(ids: any) => { setSelectedProjects(ids); setPage(1); }}
              />
              <button
                onClick={resetFilters}
                className="rounded-lg border border-[#E2E8F0] px-3.5 py-2 text-[13px] font-semibold text-[#64748B] transition hover:text-[#0F172A]"
              >
                Reset
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-[#F1F5F9] pt-3">
            <div className="relative min-w-[220px] flex-1">
              <svg
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#94A3B8]"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                placeholder="Search member, project, task, app or URL..."
                className="w-full rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] py-2 pl-9 pr-3 text-[13px] text-[#0F172A] outline-none placeholder:text-[#94A3B8] focus:border-[#2563EB]/40 focus:bg-white"
              />
            </div>
            <span className="text-[12px] text-[#94A3B8]">
              <strong className="text-[#0F172A]">{totalRows.toLocaleString()}</strong> entries ·{" "}
              <strong className="text-[#0F172A]">{totalGrouped}</strong> {dimensionLabel.toLowerCase()}s in range
            </span>
          </div>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryTile
            label="Total Time"
            value={formatHMS(totalTrackedSeconds)}
            caption={`${range.from} - ${range.to}`}
            color={config.color}
          />
          <SummaryTile label="Avg. Activity" value={`${avgActivity}%`} caption="Across filtered entries" color={series[1]} />
          <SummaryTile label="Members" value={String(uniqueMembers)} caption="Included in this report" color={series[2]} />
          <SummaryTile
            label="Entries"
            value={totalEntries.toLocaleString()}
            caption={`Across ${totalGrouped} ${dimensionLabel.toLowerCase()}s`}
            color={series[3]}
          />
        </div>

        {/* Full grouped breakdown */}
        <section className="rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#F1F5F9] px-5 py-4">
            <div>
              <h2 className="text-[15px] font-bold tracking-tight text-[#0F172A]">
                Hours by {dimensionLabel}
              </h2>
              <p className="mt-0.5 text-[11px] text-[#94A3B8]">
                All {totalGrouped} {dimensionLabel.toLowerCase()}s matching the filters
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {config.dimension === "app" && (
                <div className="flex items-center rounded-lg border border-[#E2E8F0] bg-white p-0.5">
                  {(["app", "url"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setUsageTab(tab)}
                      className={
                        "rounded-[6px] px-3 py-1.5 text-xs font-bold uppercase transition " +
                        (usageTab === tab ? "bg-[#2563EB] text-white shadow-sm" : "text-[#64748B] hover:text-[#0F172A]")
                      }
                    >
                      {tab}s
                    </button>
                  ))}
                </div>
              )}

              <div className="flex items-center rounded-lg border border-[#E2E8F0] bg-white p-0.5">
                {([
                  { id: "hours", label: "Hours" },
                  { id: "activity", label: "Activity" },
                  { id: "name", label: "A-Z" },
                ] as const).map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => setGroupSort(opt.id as any)}
                    className={
                      "rounded-[6px] px-3 py-1.5 text-xs font-semibold transition " +
                      (groupSort === opt.id ? "bg-[#2563EB] text-white shadow-sm" : "text-[#64748B] hover:text-[#0F172A]")
                    }
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              <button
                onClick={handleExportSummary}
                className="rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-xs font-bold text-[#2563EB] transition hover:border-[#2563EB]/40 hover:bg-[#2563EB]/5"
              >
                Export summary
              </button>

              <Legend items={[{ label: "Tracked hours", color: config.color }]} />
            </div>
          </header>

          <div className="max-h-[520px] overflow-y-auto p-4">
            {finalGrouped.length === 0 ? (
              <div className="py-16 text-center text-[13px] text-[#94A3B8]">
                No activity matched these filters. Widen the date range or clear the member selection.
              </div>
            ) : (
              <RankedBars
                items={finalGrouped}
                color={config.color}
                formatValue={(n: number) => formatHoursAsHMS(n)}
                secondaryLabel="Avg. activity"
              />
            )}
          </div>
        </section>

        {/* Detailed rows */}
        <section className="overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#F1F5F9] px-5 py-4">
            <div>
              <h2 className="text-[15px] font-bold tracking-tight text-[#0F172A]">Detailed Activity</h2>
              <p className="mt-0.5 text-[11px] text-[#94A3B8]">
                {totalRows.toLocaleString()} rows · page {safePage} of {totalPages}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">Rows</span>
              <div className="flex items-center rounded-lg border border-[#E2E8F0] bg-white p-0.5">
                {PAGE_SIZES.map((size) => (
                  <button
                    key={size}
                    onClick={() => { setPageSize(size); setPage(1); }}
                    className={
                      "rounded-[6px] px-2.5 py-1.5 text-xs font-semibold transition " +
                      (pageSize === size ? "bg-[#2563EB] text-white shadow-sm" : "text-[#64748B] hover:text-[#0F172A]")
                    }
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>
          </header>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] border-collapse text-left">
              <thead>
                <tr className="bg-[#F8FAFC]">
                  <SortHeader label="Date" sortKey="date" active={sortKey} desc={sortDesc} onSort={handleSort} />
                  <SortHeader label="Member" sortKey="member" active={sortKey} desc={sortDesc} onSort={handleSort} />
                  <SortHeader label="Project" sortKey="project" active={sortKey} desc={sortDesc} onSort={handleSort} />
                  <SortHeader label="Task" sortKey="task" active={sortKey} desc={sortDesc} onSort={handleSort} />
                  <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-[#64748B]">App / URL</th>
                  <SortHeader label="Hours" sortKey="hours" active={sortKey} desc={sortDesc} onSort={handleSort} align="right" />
                  <SortHeader label="Activity" sortKey="activity" active={sortKey} desc={sortDesc} onSort={handleSort} align="right" />
                </tr>
              </thead>
              <tbody>
                {pageRows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-5 py-16 text-center text-[13px] text-[#94A3B8]">
                      Nothing to show for the current filters.
                    </td>
                  </tr>
                )}
                {pageRows.map((r: any) => (
                  <tr key={r.id} className="border-t border-[#F1F5F9] transition hover:bg-[#F8FAFC]">
                    <td className="whitespace-nowrap px-5 py-3 text-[12px] font-semibold tabular-nums text-[#64748B]">
                      {r.date}
                    </td>
                    <td className="px-5 py-3">
                      <div className="text-[13px] font-semibold text-[#0F172A]">{r.member}</div>
                      <div className="text-[11px] text-[#94A3B8]">{r.role}</div>
                    </td>
                    <td className="px-5 py-3 text-[12px] text-[#64748B]">{r.project}</td>
                    <td className="px-5 py-3 text-[12px] text-[#64748B]">{r.task}</td>
                    <td className="px-5 py-3">
                      <div className="text-[12px] text-[#64748B]">{r.app}</div>
                      <div className="text-[11px] text-[#94A3B8]">{r.url}</div>
                    </td>
                    <td className="px-5 py-3 text-right text-[13px] font-bold tabular-nums text-[#0F172A]">
                      {formatHMS(r.seconds)}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[#F1F5F9]">
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${r.activity}%`, background: config.color }}
                          />
                        </div>
                        <span className="w-9 text-right text-[12px] font-bold tabular-nums text-[#0F172A]">
                          {r.activity}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#F1F5F9] px-5 py-3">
            <span className="text-[11px] text-[#94A3B8]">
              Showing {totalRows === 0 ? 0 : (safePage - 1) * pageSize + 1}-
              {Math.min(safePage * pageSize, totalRows)} of {totalRows.toLocaleString()}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage(1)}
                disabled={safePage === 1}
                className="rounded-lg border border-[#E2E8F0] px-2.5 py-1.5 text-xs font-semibold text-[#64748B] transition enabled:hover:text-[#0F172A] disabled:opacity-40"
              >
                First
              </button>
              <button
                onClick={() => setPage(safePage - 1)}
                disabled={safePage === 1}
                className="rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-xs font-semibold text-[#64748B] transition enabled:hover:text-[#0F172A] disabled:opacity-40"
              >
                Prev
              </button>
              <span className="px-2 text-xs font-bold tabular-nums text-[#0F172A]">
                {safePage} / {totalPages}
              </span>
              <button
                onClick={() => setPage(safePage + 1)}
                disabled={safePage === totalPages}
                className="rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-xs font-semibold text-[#64748B] transition enabled:hover:text-[#0F172A] disabled:opacity-40"
              >
                Next
              </button>
              <button
                onClick={() => setPage(totalPages)}
                disabled={safePage === totalPages}
                className="rounded-lg border border-[#E2E8F0] px-2.5 py-1.5 text-xs font-semibold text-[#64748B] transition enabled:hover:text-[#0F172A] disabled:opacity-40"
              >
                Last
              </button>
            </div>
          </div>
        </section>
      </div>
    </V2Shell>
  );
};
