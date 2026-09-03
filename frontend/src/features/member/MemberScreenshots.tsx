import React, { useMemo, useState } from "react";
import { MemberShell } from "./MemberShell";
import { Card, EmptyState, ErrorNote, Spinner } from "./MemberUi";
import { useGetScreenshotsQuery } from "../../store/api/screenshotsApi";
import type { TimeEntryScreenshot } from "../../store/api/screenshotsApi";
import { InlineRefreshIndicator } from "../../components/InlineRefreshIndicator";
import { DateRangeFilter, DEFAULT_RANGE } from "../dashboard/v2/filters";
import type { DateRange } from "../dashboard/v2/filters";
import { formatISTDate, formatISTTime } from "../../utils/duration";

/**
 * The member's own screenshots.
 *
 * This page reads `/time-entry-screenshots`, which pins a member to their own
 * captures. Client-side screenshot capture is not implemented yet (see
 * CLAUDE.md §5.3), so for most members the honest answer today is an empty
 * state that says why — not a grid of stand-in images. If and when a client
 * starts writing captures, they appear here with no further change.
 *
 * `file_path` is free text in the schema: it may be a fetchable URL or a path
 * on the machine that took the shot. Only the former is rendered as an image;
 * the latter is listed as a record, because drawing a broken tile would imply
 * an image exists where none can be loaded.
 */

const IST = "Asia/Kolkata";

/** The IST calendar day a capture belongs to, as `YYYY-MM-DD`. */
const istDayOf = (iso: string) => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
  return parts;
};

const isViewable = (path: string) => /^https?:\/\//i.test(path || "");

const ScreenshotTile: React.FC<{ shot: TimeEntryScreenshot }> = ({ shot }) => (
  <figure className="overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-sm transition hover:shadow-md">
    {isViewable(shot.file_path) ? (
      <a href={shot.file_path} target="_blank" rel="noreferrer" className="block">
        <img
          src={shot.file_path}
          alt={`Screen captured at ${formatISTTime(shot.captured_at)}`}
          loading="lazy"
          className="aspect-video w-full bg-[#F1F5F9] object-cover"
        />
      </a>
    ) : (
      <div className="flex aspect-video w-full items-center justify-center bg-[#F8FAFC] px-4 text-center">
        <div>
          <svg
            className="mx-auto h-6 w-6 text-[#CBD5E1]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.5"
              d="M3 3l18 18M10.5 10.6a2 2 0 002.9 2.8M6.6 6.6A9.8 9.8 0 003 12s3 6 9 6a9.3 9.3 0 004.4-1.1M9.9 5.2A9.9 9.9 0 0112 5c6 0 9 6 9 6a15 15 0 01-2.2 3"
            />
          </svg>
          <p className="mt-2 text-[11px] font-semibold text-[#94A3B8]">Image not retrievable</p>
          <p className="mt-0.5 truncate text-[10px] text-[#CBD5E1]" title={shot.file_path}>
            {shot.file_path}
          </p>
        </div>
      </div>
    )}
    <figcaption className="flex items-center justify-between gap-2 px-3 py-2 text-[11px]">
      <span className="font-bold text-[#0F172A]">{formatISTTime(shot.captured_at)}</span>
      <span className="text-[#94A3B8]">Monitor {shot.monitor_number}</span>
    </figcaption>
  </figure>
);

export const MemberScreenshots: React.FC = () => {
  const [range, setRange] = useState<DateRange>(DEFAULT_RANGE);
  const { data = [], isLoading, isFetching, isError } = useGetScreenshotsQuery({ limit: 500 });

  /**
   * The endpoint takes no date range — it returns the most recent captures —
   * so the selected range is applied here, over IST calendar days, to match
   * every other date filter in the app.
   */
  const groups = useMemo(() => {
    const byDay = new Map<string, TimeEntryScreenshot[]>();
    data
      .filter((shot) => {
        const day = istDayOf(shot.captured_at);
        return day >= range.from && day <= range.to;
      })
      .sort((a, b) => new Date(b.captured_at).getTime() - new Date(a.captured_at).getTime())
      .forEach((shot) => {
        const day = istDayOf(shot.captured_at);
        byDay.set(day, [...(byDay.get(day) || []), shot]);
      });
    return [...byDay.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [data, range]);

  const shownCount = groups.reduce((sum, [, shots]) => sum + shots.length, 0);

  return (
    <MemberShell
      title="My Screenshots"
      subtitle="Screens captured while you were tracking time."
      actions={<InlineRefreshIndicator active={isFetching && !isLoading} />}
    >
      <div className="w-full space-y-6 pb-20">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <DateRangeFilter value={range} onChange={setRange} />
            <span className="text-[12px] font-semibold text-[#64748B]">
              {shownCount} capture{shownCount === 1 ? "" : "s"} in range
            </span>
          </div>
        </Card>

        {isError && <ErrorNote message="Your screenshots could not be loaded. Please try again." />}

        {isLoading ? (
          <Spinner label="Loading your screenshots…" />
        ) : groups.length === 0 ? (
          <Card>
            <EmptyState
              message="No screenshots for this date range."
              hint={
                data.length === 0
                  ? "Screenshot capture is not enabled in the desktop client yet, so nothing has been recorded against your account. This page will fill in on its own once captures start arriving."
                  : "You have captures outside this range — widen the dates to see them."
              }
            />
          </Card>
        ) : (
          groups.map(([day, shots]) => (
            <Card key={day} title={formatISTDate(`${day}T00:00:00Z`)}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {shots.map((shot) => (
                  <ScreenshotTile key={shot.id} shot={shot} />
                ))}
              </div>
            </Card>
          ))
        )}
      </div>
    </MemberShell>
  );
};
