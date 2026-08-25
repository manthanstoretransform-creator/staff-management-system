import React, { useState } from "react";
import { V2Shell } from "./V2Shell";
import { Sparkline, TrendAreaChart, RankedBars, Donut, Legend } from "./charts";
import { CURRENT_MONTH, getDashboardData, monthByKey } from "./mockData";
import { brand, series } from "./theme";
import { useNavigate } from "react-router-dom";

export const DashboardV2: React.FC = () => {
  const [monthKey] = useState(CURRENT_MONTH);
  const data = getDashboardData(monthKey);
  const navigate = useNavigate();

  const formatDelta = (pct: number) => {
    if (pct > 0) return `+${pct.toFixed(1)}%`;
    if (pct < 0) return `${pct.toFixed(1)}%`;
    return "0%";
  };

  const trendColor = (pct: number) => {
    if (pct > 0) return "text-emerald-500";
    if (pct < 0) return "text-rose-500";
    return "text-slate-500";
  };

  const kpiCard = (
    title: string,
    value: string | number,
    delta: number,
    trend: number[],
    color: string
  ) => (
    <div className="flex flex-col justify-between rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-wider text-[#94A3B8]">{title}</div>
          <div className="mt-1 text-3xl font-extrabold text-[#0F172A]">{value}</div>
        </div>
        <div className={`mt-1 flex items-center gap-1 text-[13px] font-bold ${trendColor(delta)}`}>
          {delta > 0 ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
          ) : delta < 0 ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          ) : null}
          <span>{formatDelta(delta)}</span>
        </div>
      </div>
      <div className="mt-6 h-10 w-full opacity-70">
        <Sparkline values={trend} color={color} height={40} />
      </div>
    </div>
  );

  return (
    <V2Shell
      title="Dashboard Overview"
      subtitle={`Here's what's happening this ${data.month.label.toLowerCase()}.`}
    >
      <div className="mx-auto max-w-[1200px] space-y-8 pb-20">
        {/* KPIs */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpiCard("Monthly Activity", `${data.kpis.monthlyActivity.value}%`, data.kpis.monthlyActivity.deltaPct, data.kpis.monthlyActivity.trend, series[0])}
          {kpiCard("Total Hours", `${data.kpis.totalProductivity.value}h`, data.kpis.totalProductivity.deltaPct, data.kpis.totalProductivity.trend, series[1])}
          {kpiCard("Active Projects", data.kpis.totalProjects.value, data.kpis.totalProjects.deltaPct, data.kpis.totalProjects.trend, series[2])}
          {kpiCard("Team Members", data.kpis.totalEmployees.value, data.kpis.totalEmployees.deltaPct, data.kpis.totalEmployees.trend, series[3])}
        </div>

        {/* Trend Area Chart */}
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-[13px] font-bold uppercase tracking-wider text-[#64748B]">Time Tracked (Past 14 Days)</h3>
            <Legend
              items={[
                { label: "Tracked App Time", color: series[0] },
                { label: "Manual Time", color: brand.muted },
              ]}
            />
          </div>
          <div className="h-64 w-full">
            <TrendAreaChart
              labels={data.trend.labels}
              seriesList={[
                { label: "Tracked App Time", values: data.trend.tracked, color: series[0] },
                { label: "Manual Time", values: data.trend.manual, color: brand.muted },
              ]}
              unit="h"
            />
          </div>
        </div>

        {/* Top 3 Lists */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Top Projects */}
          <div className="flex flex-col rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[13px] font-bold uppercase tracking-wider text-[#64748B]">Top Projects</h3>
              <button onClick={() => navigate('/dashboard-v2/reports/projects')} className="text-[11px] font-bold text-[#2563EB] hover:underline">View All</button>
            </div>
            <RankedBars
              items={data.projects.slice(0, 5).map(p => ({
                id: p.id,
                name: p.name,
                value: p.hours,
                meta: `${p.activity}% avg`,
                secondary: p.activity
              }))}
              color={series[2]}
              formatValue={(n) => `${n.toFixed(1)}h`}
            />
          </div>

          {/* Top Members */}
          <div className="flex flex-col rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[13px] font-bold uppercase tracking-wider text-[#64748B]">Top Members</h3>
              <button onClick={() => navigate('/dashboard-v2/reports/members')} className="text-[11px] font-bold text-[#2563EB] hover:underline">View All</button>
            </div>
            <RankedBars
              avatars
              items={data.members.slice(0, 5).map(m => ({
                id: m.id,
                name: m.name,
                value: m.hours,
                meta: `${m.activity}% active`,
                secondary: m.activity
              }))}
              color={series[4]}
              formatValue={(n) => `${n.toFixed(1)}h`}
            />
          </div>

          {/* Apps Breakdown Donut */}
          <div className="flex flex-col rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[13px] font-bold uppercase tracking-wider text-[#64748B]">Top Apps</h3>
              <button onClick={() => navigate('/dashboard-v2/reports/apps')} className="text-[11px] font-bold text-[#2563EB] hover:underline">View All</button>
            </div>
            <div className="flex flex-1 items-center justify-center py-4">
              <Donut
                size={180}
                slices={data.apps.slice(0, 4).map((a, i) => ({
                  label: a.name,
                  value: a.hours,
                  color: series[i % series.length]
                }))}
                centerLabel="Total App Time"
                centerValue={`${data.apps.reduce((sum, a) => sum + a.hours, 0).toFixed(0)}h`}
              />
            </div>
          </div>
        </div>
      </div>
    </V2Shell>
  );
};
