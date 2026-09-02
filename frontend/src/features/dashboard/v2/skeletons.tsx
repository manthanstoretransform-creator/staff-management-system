import React from "react";

/**
 * Placeholder shapes shown while the dashboard's first request of a page load
 * is in flight. They mirror the real layout — same card frames, same grid, same
 * heights — so the page does not jump when the data lands.
 *
 * These are shapes, not values: nothing here is derived from, or stands in for,
 * real numbers. Once the request settles the skeleton is replaced outright.
 */

const Shimmer: React.FC<{ className?: string; style?: React.CSSProperties }> = ({
  className = "",
  style,
}) => <div className={`animate-pulse rounded bg-[#E2E8F0] ${className}`} style={style} />;

const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({
  className = "",
  children,
}) => (
  <div className={`rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-sm ${className}`}>
    {children}
  </div>
);

const KpiCardSkeleton: React.FC = () => (
  <Card className="flex flex-col justify-between">
    <div className="flex items-start justify-between gap-4">
      <div className="w-full">
        <Shimmer className="h-3 w-24" />
        <Shimmer className="mt-3 h-8 w-32" />
      </div>
      <Shimmer className="h-4 w-12" />
    </div>
    <Shimmer className="mt-6 h-10 w-full" />
  </Card>
);

/** One row of the ranked-bar lists: rank/avatar, label, bar, value. */
const RankedRowSkeleton: React.FC<{ avatar?: boolean; width: string }> = ({ avatar, width }) => (
  <div className="flex items-center gap-3">
    <Shimmer className={avatar ? "h-8 w-8 shrink-0 rounded-full" : "h-6 w-6 shrink-0 rounded-md"} />
    <div className="min-w-0 flex-1">
      <div className="flex items-center justify-between gap-3">
        <Shimmer className={`h-3 ${width}`} />
        <Shimmer className="h-3 w-16 shrink-0" />
      </div>
      <Shimmer className="mt-2 h-2 w-full" />
    </div>
  </div>
);

const ROW_WIDTHS = ["w-40", "w-32", "w-44", "w-28", "w-36"];

const ListCardSkeleton: React.FC<{ avatars?: boolean }> = ({ avatars }) => (
  <Card className="flex flex-col">
    <div className="mb-4 flex items-center justify-between">
      <Shimmer className="h-3 w-28" />
      <Shimmer className="h-3 w-14" />
    </div>
    <div className="space-y-4">
      {ROW_WIDTHS.map((width, i) => (
        <RankedRowSkeleton key={i} avatar={avatars} width={width} />
      ))}
    </div>
  </Card>
);

const DonutCardSkeleton: React.FC = () => (
  <Card className="flex flex-col">
    <div className="mb-4 flex items-center justify-between">
      <Shimmer className="h-3 w-24" />
      <Shimmer className="h-3 w-14" />
    </div>
    <div className="flex flex-1 flex-col items-center justify-center gap-5 py-4">
      <Shimmer className="h-[180px] w-[180px] rounded-full" />
      <div className="w-full space-y-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-2">
            <Shimmer className="h-3 w-3 rounded-full" />
            <Shimmer className="h-3 w-24" />
          </div>
        ))}
      </div>
    </div>
  </Card>
);

export const DashboardSkeleton: React.FC = () => (
  <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
    {/* KPI row */}
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <KpiCardSkeleton key={i} />
      ))}
    </div>

    {/* Trend chart */}
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <Shimmer className="h-3 w-64" />
        <div className="flex items-center gap-4">
          <Shimmer className="h-3 w-24" />
          <Shimmer className="h-3 w-24" />
        </div>
      </div>
      <div className="flex h-64 w-full items-end gap-2">
        {[45, 70, 30, 85, 55, 65, 40, 75, 50, 60, 35, 80].map((height, i) => (
          <Shimmer key={i} className="flex-1" style={{ height: `${height}%` }} />
        ))}
      </div>
    </Card>

    {/* Top lists */}
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <ListCardSkeleton />
      <ListCardSkeleton avatars />
      <DonutCardSkeleton />
    </div>
  </div>
);
