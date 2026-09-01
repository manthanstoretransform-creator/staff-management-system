import React, { useMemo, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { V2Shell } from "./V2Shell";
import { Sparkline, TrendAreaChart, Donut, useInView } from "./charts";
import {
  DateRangeFilter,
  DEFAULT_RANGE,
  MemberMultiSelect,
  ProjectMultiSelect,
  rangeForMonth,
} from "./filters";
import type { DateRange } from "./filters";
import { monthByKey } from "./mockData";
import { useGetMembersQuery } from "../../../store/api/membersApi";
import { useGetAllProjectsQuery } from "../../../store/api/projectsApi";

type ReportId = "projects" | "members" | "tasks" | "apps";

const REPORTS: Record<
  ReportId,
  { title: string; subtitle: string; dimension: string; dimensionLabel: string; color: string }
> = {
  projects: {
    title: "Project-Wise Activity Report",
    subtitle: "Every project in the selected period, not just the dashboard top 10",
    dimension: "project",
    dimensionLabel: "Project",
    color: "#2563EB",
  },
  members: {
    title: "Member-Wise Activity Report",
    subtitle: "Every member in the selected period, not just the dashboard top 10",
    dimension: "member",
    dimensionLabel: "Member",
    color: "#8B5CF6",
  },
  tasks: {
    title: "Top Tasks Report",
    subtitle: "Every task in the selected period, not just the dashboard top 10",
    dimension: "task",
    dimensionLabel: "Task",
    color: "#10B981",
  },
  apps: {
    title: "Apps & URLs Usage Report",
    subtitle: "Every application and website in the selected period",
    dimension: "app",
    dimensionLabel: "App",
    color: "#F59E0B",
  },
};

/* ------------------------------------------------------------------ */
/* Custom Animated Ranked Bars for "Hours by Project"                  */
/* ------------------------------------------------------------------ */
const AnimatedRankedBars: React.FC<{ items: any[]; formatValue: (n: number) => string }> = ({ items, formatValue }) => {
  const { ref, inView } = useInView({ threshold: 0.1, triggerOnce: false });
  const max = Math.max(...items.map((i) => i.value)) || 1;

  return (
    <ul ref={ref} className="flex flex-col gap-2">
      {items.map((item, index) => {
        const percent = Math.max((item.value / max) * 100, 1);
        return (
          <li key={item.id} className="group relative flex items-center gap-4 py-2 transition-all">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-[#F1F5F9] text-[11px] font-bold text-[#64748B]">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-[13px] font-bold text-[#0F172A]">{item.name}</span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-[6px] flex-1 overflow-hidden rounded-full bg-[#F1F5F9]">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-400 transition-all duration-1000 ease-out"
                    style={{ width: inView ? `${percent}%` : "0%" }}
                  />
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: item.meta === "Active" ? "#10B981" : item.meta === "Pending" ? "#F59E0B" : "#94A3B8" }}
                  />
                  <span className="text-[10px] uppercase tracking-wider text-[#94A3B8]">{item.meta}</span>
                </div>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[13px] font-extrabold text-[#0F172A]">{formatValue(item.value)}</div>
              <div className="text-[11px] font-semibold text-[#94A3B8]">{item.secondary}%</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
};

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

  const { data: membersResponse } = useGetMembersQuery({ limit: 5000 });
  const membersData = membersResponse?.items ?? [];

  const { data: allProjects = [] } = useGetAllProjectsQuery();

  const config = REPORTS[reportId as ReportId];

  // Dummy Grouped Data
  const groupedData = useMemo(() => {
    return {
      summary: {
        total_hours: 124.50,
        average_activity_percentage: 82,
        total_members: 3,
        total_entries: 42
      },
      grouped_data: [
        { id: "1", name: "Project A", tracked_hours: 45.20, activity_percentage: 36.3, meta_label: "Active" },
        { id: "2", name: "Project B", tracked_hours: 32.10, activity_percentage: 25.8, meta_label: "Pending" },
        { id: "3", name: "Project C", tracked_hours: 21.00, activity_percentage: 16.8, meta_label: "Active" },
        { id: "4", name: "Project D", tracked_hours: 15.50, activity_percentage: 12.4, meta_label: "Inactive" },
        { id: "5", name: "Project E", tracked_hours: 10.70, activity_percentage: 8.6, meta_label: "Active" },
      ]
    };
  }, []);

  const finalGrouped = useMemo(() => {
    return (groupedData.grouped_data || []).map((item: any) => ({
      id: String(item.id),
      name: item.name,
      value: item.tracked_hours || 0,
      secondary: item.activity_percentage || 0,
      meta: item.meta_label,
    })).sort((a, b) => b.value - a.value);
  }, [groupedData]);

  const summary = groupedData?.summary;
  const totalHours = summary?.total_hours || 0;
  const avgActivity = summary?.average_activity_percentage || 0;
  const uniqueMembers = summary?.total_members || 0;
  const totalEntries = summary?.total_entries || 0;
  const totalGrouped = finalGrouped.length;

  if (!config) return <Navigate to="/dashboard" replace />;

  const resetFilters = () => {
    setRange(monthParam ? rangeForMonth(monthParam) : DEFAULT_RANGE);
    setSelectedMembers([]);
    setSelectedProjects([]);
  };

  // Dummy Trend Data
  const trendLabels = ["Jul 22", "", "", "Jul 27", "", "", "Aug 01", "", "", "Aug 06", "", "", "Aug 11", "", "", "Aug 16", "", "", "Aug 20"];
  const trendSeries = [
    { label: "Activity %", values: [20, 30, 45, 25, 40, 45, 30, 20, 35, 45, 30, 20, 15, 25, 20, 35, 20, 35, 25], color: "#10B981" },
    { label: "Hours", values: [10, 15, 35, 45, 25, 30, 20, 35, 25, 30, 25, 45, 55, 60, 40, 35, 25, 40, 30], color: "#2563EB" },
  ];

  // Dummy Donut Data
  const donutSlices = [
    { label: "Project A", value: 45.2, color: "#F59E0B" },
    { label: "Project B", value: 32.1, color: "#3B82F6" },
    { label: "Project C", value: 21.0, color: "#8B5CF6" },
    { label: "Project D", value: 15.5, color: "#10B981" },
    { label: "Project E", value: 10.7, color: "#EF4444" },
  ];

  return (
    <V2Shell
      title={config.title}
      subtitle={config.subtitle}
      breadcrumb={
        <button
          onClick={() => navigate("/dashboard")}
          className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#64748B] transition hover:text-[#2563EB]"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M15 19l-7-7 7-7" />
          </svg>
          Dashboard
          {monthParam && <span className="normal-case text-[#94A3B8]">· {monthByKey(monthParam).label}</span>}
        </button>
      }
      actions={
        <>
          <div className="hidden items-center rounded-lg border border-[#E2E8F0] bg-white p-0.5 lg:flex">
            {(Object.keys(REPORTS) as ReportId[]).map((id) => (
              <button
                key={id}
                onClick={() => navigate(`/dashboard/reports/${id}${monthParam ? `?month=${monthParam}` : ""}`)}
                className={
                  "rounded-[6px] px-4 py-2 text-xs font-bold capitalize transition " +
                  (id === reportId ? "bg-[#2563EB] text-white shadow-sm" : "text-[#64748B] hover:text-[#0F172A]")
                }
              >
                {id}
              </button>
            ))}
          </div>
          <button className="flex items-center gap-1.5 rounded-lg bg-[#0F172A] px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#1E293B]">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
            </svg>
            Export CSV
          </button>
        </>
      }
    >
      <div className="mx-auto max-w-[1400px] space-y-6">
        
        {/* Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#E2E8F0] bg-white p-2 pl-4 shadow-sm">
          <DateRangeFilter value={range} onChange={(r: any) => { setRange(r) }} />
          <div className="flex flex-wrap items-center gap-2">
            <MemberMultiSelect members={membersData} selected={selectedMembers} onChange={(ids: any) => { setSelectedMembers(ids) }} />
            <ProjectMultiSelect projects={allProjects} selected={selectedProjects} onChange={(ids: any) => { setSelectedProjects(ids) }} />
            <button
              onClick={resetFilters}
              className="rounded-lg border border-[#E2E8F0] px-4 py-2 text-[13px] font-bold text-[#64748B] transition hover:bg-[#F8FAFC] hover:text-[#0F172A]"
            >
              Reset
            </button>
          </div>
        </div>

        {/* Summary Tiles */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {/* Tile 1: Total Hours */}
          <div className="relative overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#2563EB] text-white">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">Total Hours</span>
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div className="relative z-10">
                <div className="text-[32px] font-extrabold leading-none tracking-tight text-[#0F172A]">{totalHours.toFixed(2)}h</div>
                <div className="mt-1.5 text-[11px] text-[#94A3B8]">{range.from} - {range.to}</div>
              </div>
              <div className="absolute bottom-0 right-0 h-16 w-32 opacity-70">
                <Sparkline values={[2,4,3,6,5,8,7,9]} color="#2563EB" height={64} />
              </div>
            </div>
          </div>

          {/* Tile 2: Avg Activity */}
          <div className="relative overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#10B981] text-white">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">Avg. Activity</span>
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div className="relative z-10">
                <div className="text-[32px] font-extrabold leading-none tracking-tight text-[#0F172A]">{avgActivity}%</div>
                <div className="mt-1.5 text-[11px] text-[#94A3B8]">Across filtered entries</div>
              </div>
              <div className="absolute bottom-4 right-4 flex items-end gap-1">
                {[4, 6, 3, 7, 5, 8].map((h, i) => (
                  <div key={i} className="w-1.5 rounded-full bg-[#10B981] opacity-40 animate-pulse" style={{ height: h * 4, animationDelay: `${i * 100}ms` }} />
                ))}
              </div>
            </div>
          </div>

          {/* Tile 3: Members */}
          <div className="relative overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#8B5CF6] text-white">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">Members</span>
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div className="relative z-10">
                <div className="text-[32px] font-extrabold leading-none tracking-tight text-[#0F172A]">{uniqueMembers}</div>
                <div className="mt-1.5 text-[11px] text-[#94A3B8]">Included in this report</div>
              </div>
              <div className="absolute -right-2 top-10 flex h-20 w-20 items-center justify-center rounded-full bg-[#8B5CF6]/10">
                <svg className="h-10 w-10 text-[#8B5CF6]" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
              </div>
            </div>
          </div>

          {/* Tile 4: Entries */}
          <div className="relative overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F59E0B] text-white">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">Entries</span>
            </div>
            <div className="mt-4 flex items-end justify-between">
              <div className="relative z-10">
                <div className="text-[32px] font-extrabold leading-none tracking-tight text-[#0F172A]">{totalEntries}</div>
                <div className="mt-1.5 text-[11px] text-[#94A3B8]">Across {totalGrouped} projects</div>
              </div>
              <div className="absolute -right-2 top-10 flex h-20 w-20 items-center justify-center rounded-full bg-[#F59E0B]/10">
                <svg className="h-10 w-10 text-[#F59E0B]" fill="currentColor" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
              </div>
            </div>
          </div>
        </div>

        {/* 2-Column Grid Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          
          {/* Left Column: Hours by Project */}
          <div className="flex flex-col lg:col-span-7">
            <section className="flex flex-1 flex-col rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
              <header className="flex flex-wrap items-center justify-between gap-3 px-6 py-5">
                <div>
                  <h2 className="text-[16px] font-bold tracking-tight text-[#0F172A]">Hours by Project</h2>
                  <p className="mt-0.5 text-[12px] text-[#94A3B8]">All {totalGrouped} projects matching the filters</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center rounded-lg border border-[#E2E8F0] bg-white p-0.5">
                    <button className="rounded-[6px] bg-[#2563EB] px-4 py-1.5 text-xs font-bold text-white shadow-sm transition">Hours</button>
                    <button className="rounded-[6px] px-4 py-1.5 text-xs font-semibold text-[#64748B] transition hover:text-[#0F172A]">Activity</button>
                    <button className="rounded-[6px] px-4 py-1.5 text-xs font-semibold text-[#64748B] transition hover:text-[#0F172A]">A-Z</button>
                  </div>
                  <button className="text-[#94A3B8] hover:text-[#0F172A]">
                    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
                  </button>
                </div>
              </header>

              <div className="flex px-6 pb-2">
                <span className="w-10 text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]"></span>
                <span className="flex-1 text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">Project</span>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">Total Hours</span>
              </div>

              <div className="flex-1 px-4 pb-4">
                <AnimatedRankedBars items={finalGrouped} formatValue={(n) => `${n.toFixed(2)}h`} />
              </div>

              <div className="mt-auto border-t border-[#F1F5F9] px-6 py-4">
                <button className="flex w-full items-center justify-center gap-1 text-[13px] font-bold text-[#64748B] transition hover:text-[#0F172A]">
                  View all projects
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                </button>
              </div>
            </section>
          </div>

          {/* Right Column: Trend & Donut Charts */}
          <div className="flex flex-col gap-6 lg:col-span-5">
            
            {/* Activity Trend */}
            <section className="rounded-2xl border border-[#E2E8F0] bg-white p-6 shadow-sm">
              <header className="mb-4 flex items-center justify-between">
                <h2 className="text-[16px] font-bold tracking-tight text-[#0F172A]">Activity Trend</h2>
                <div className="flex items-center gap-1 rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-[12px] font-semibold text-[#0F172A]">
                  Daily
                  <svg className="h-3.5 w-3.5 text-[#64748B]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
                </div>
              </header>
              <div className="mb-6 flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#10B981]" />
                  <span className="text-[12px] text-[#64748B]">Activity %</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#2563EB]" />
                  <span className="text-[12px] text-[#64748B]">Hours</span>
                </div>
              </div>
              <div className="h-48 w-full">
                <TrendAreaChart labels={trendLabels} seriesList={trendSeries} height={192} />
              </div>
            </section>

            {/* Hours Distribution */}
            <section className="flex flex-1 flex-col rounded-2xl border border-[#E2E8F0] bg-white p-6 shadow-sm">
              <header className="mb-6">
                <h2 className="text-[16px] font-bold tracking-tight text-[#0F172A]">Hours Distribution</h2>
              </header>
              <div className="flex flex-1 items-center justify-between gap-6">
                <div className="flex shrink-0 items-center justify-center">
                  <Donut slices={donutSlices} size={150} centerLabel="Total" centerValue="124.50h" />
                </div>
                <div className="flex-1">
                  <ul className="flex flex-col gap-3">
                    {donutSlices.map((slice) => (
                      <li key={slice.label} className="flex items-center justify-between text-[12px]">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
                          <span className="font-bold text-[#0F172A]">{slice.label}</span>
                        </div>
                        <div className="text-right">
                          <span className="font-bold text-[#64748B]">{slice.value.toFixed(2)}h</span>
                          <span className="ml-1 text-[#94A3B8]">({((slice.value / 124.5) * 100).toFixed(1)}%)</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>

          </div>
        </div>
      </div>
    </V2Shell>
  );
};
