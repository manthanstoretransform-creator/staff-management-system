import React, { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MemberShell } from "./MemberShell";
import { Card, EmptyState, ErrorNote, Spinner } from "./MemberUi";
import { useAuth } from "../auth/authContext";
import { useGetScreenshotDayQuery } from "../../store/api/screenshotsApi";
import type { ScreenshotDay } from "../../store/api/screenshotsApi";
import { DayFilter, istTodayIso } from "../screenshots/DayFilter";
import { groupWindowsByHour } from "../screenshots/hours";
import { HourRow } from "../screenshots/HourRow";
import { ScreenshotLightbox } from "../screenshots/ScreenshotLightbox";
import type { LightboxItem } from "../screenshots/ScreenshotLightbox";
import { InlineRefreshIndicator } from "../../components/InlineRefreshIndicator";
import { formatHMS, formatISTDate } from "../../utils/duration";

/**
 * The member's own screenshots.
 *
 * This reads `/time-entry-screenshots/day`, which pins a caller who cannot see
 * past themselves to their own captures — an employee cannot widen it, and this
 * screen never offers a way to try. The day grouping comes from the server, so
 * a capture lands on the IST day the person actually worked rather than on
 * whichever UTC day its timestamp happens to fall in.
 *
 * The layout is the admin screen's, minus the roster: today by default, hour
 * rows headed by the time worked in that hour, and the same lightbox — so a
 * member sees their day exactly as the person reviewing it does.
 *
 * The image itself comes from `/time-entry-screenshots/{id}/view`, which streams
 * the bytes behind the same permission check. The stored `file_path` is a
 * logical Google Drive path, not a fetchable URL, so rendering it in an `img`
 * tag produced a broken tile for every capture; `AuthedImage` fetches the view
 * route with the bearer token instead.
 */

const itemsOfDay = (day: ScreenshotDay, subjectName: string): LightboxItem[] =>
  [...day.windows]
    .sort((a, b) => a.window_start.localeCompare(b.window_start))
    .flatMap((window) => window.screenshots.map((shot) => ({ shot, window, subjectName })));

export const MemberScreenshots: React.FC = () => {
  const { currentUser } = useAuth();
  const [searchParams] = useSearchParams();

  // The desktop client holds only the last few days of screenshots and links
  // here for anything older, handing the day it was showing over as
  // ?start=&end= — the pair the Reports pages already accept. Both carry the
  // same date, because this page shows exactly one day; `start` is the one
  // read. Without this the link landed on today and the member had to find
  // the date again by hand.
  const initialDay = (): string => {
    const start = searchParams.get("start");
    // Anything that is not a plain ISO date is ignored rather than passed to
    // the API: the value comes from the address bar.
    return start && /^\d{4}-\d{2}-\d{2}$/.test(start) ? start : istTodayIso();
  };

  const [day, setDay] = useState<string>(initialDay);
  const [viewer, setViewer] = useState<{ items: LightboxItem[]; index: number } | null>(null);

  const { data, isLoading, isFetching, isError } = useGetScreenshotDayQuery({
    from: day,
    to: day,
  });

  /**
   * The response is a list of members; for this caller it is either empty or a
   * single entry — themselves. Reading it that way rather than indexing blindly
   * keeps the page correct if it is ever opened by someone with wider scope.
   */
  const days: ScreenshotDay[] = useMemo(() => {
    const members = data?.members ?? [];
    const mine = members.find((m) => m.user_id === currentUser?.id) ?? members[0];
    return mine?.days ?? [];
  }, [data, currentUser]);

  const myName = currentUser?.name ?? "You";
  const totalShots = days.reduce((sum, entry) => sum + entry.screenshot_count, 0);
  const totalWorked = days.reduce((sum, entry) => sum + (entry.tracked_seconds ?? 0), 0);

  return (
    <MemberShell
      title="My Screenshots"
      subtitle="Screens captured while you were tracking time."
      actions={<InlineRefreshIndicator active={isFetching && !isLoading} />}
    >
      <div className="w-full space-y-6 pb-20">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <DayFilter value={day} onChange={setDay} />
            <span className="text-[12px] font-semibold text-[#64748B]">
              {totalShots} capture{totalShots === 1 ? "" : "s"} · {formatHMS(totalWorked)} worked
            </span>
          </div>
        </Card>

        {isError && <ErrorNote message="Your screenshots could not be loaded. Please try again." />}

        {isLoading ? (
          <Spinner label="Loading your screenshots…" />
        ) : days.length === 0 ? (
          <Card>
            <EmptyState
              message="No screenshots for this day."
              hint="Captures appear here once the desktop client records and uploads them for the selected date."
            />
          </Card>
        ) : (
          days.map((entry) => {
            const items = itemsOfDay(entry, myName);
            return (
              <Card
                key={entry.date}
                title={`${formatISTDate(`${entry.date}T12:00:00Z`)} — ${formatHMS(
                  entry.tracked_seconds,
                )} worked`}
              >
                <div className="space-y-8">
                  {groupWindowsByHour(entry.windows).map((block) => (
                    <HourRow
                      key={block.key}
                      block={block}
                      subjectName={myName}
                      onOpen={(shot) =>
                        setViewer({
                          items,
                          index: Math.max(
                            0,
                            items.findIndex((item) => item.shot.id === shot.id),
                          ),
                        })
                      }
                    />
                  ))}
                </div>
              </Card>
            );
          })
        )}
      </div>

      {viewer && (
        <ScreenshotLightbox
          items={viewer.items}
          index={viewer.index}
          onIndexChange={(index) =>
            setViewer((current) => (current ? { ...current, index } : current))
          }
          onClose={() => setViewer(null)}
        />
      )}
    </MemberShell>
  );
};
