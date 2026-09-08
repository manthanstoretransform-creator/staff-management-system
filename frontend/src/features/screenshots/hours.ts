import { IST_TIME_ZONE } from '../../utils/duration';
import type { ScreenshotTimelineWindow } from '../../store/api/screenshotsApi';

/**
 * Grouping a tracked day into the hour rows the screenshots page reads in.
 *
 * The API returns one entry per capture window — ten minutes at the current
 * setting — which is the right granularity to *store* and the wrong one to
 * scan: a tracked day is 50-odd rows of it. An hour is what a person actually
 * looks for ("what was he doing at 10?"), so the windows are grouped into
 * hours here and each hour's windows stay visible inside its row.
 *
 * The hour a window belongs to is resolved through the real Asia/Kolkata zone
 * rather than by adding an offset to the timestamp. IST is +05:30, so hour
 * boundaries do not line up with UTC ones, and epoch arithmetic that assumed
 * they did would file every capture in the wrong row.
 */

/** `YYYY-MM-DD HH` in IST — the identity of an hour row. */
const istHourParts = (iso: string): { key: string; hour: number } => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: IST_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hour12: false,
  }).formatToParts(new Date(iso));

  const value = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  // Intl renders midnight as "24" in some engines; both name the same hour.
  const hour = Number(value('hour')) % 24;
  return {
    key: `${value('year')}-${value('month')}-${value('day')} ${String(hour).padStart(2, '0')}`,
    hour,
  };
};

/** An hour of the 12-hour clock as a label, e.g. 13 -> "1:00 pm". */
export const hourLabel = (hour: number): string => {
  const suffix = hour < 12 ? 'am' : 'pm';
  const twelve = hour % 12 === 0 ? 12 : hour % 12;
  return `${twelve}:00 ${suffix}`;
};

export interface HourBlock {
  /** Stable across renders: the IST date and hour this row covers. */
  key: string;
  /** e.g. "10:00 am". */
  startLabel: string;
  /** e.g. "11:00 am". */
  endLabel: string;
  windows: ScreenshotTimelineWindow[];
  /**
   * Time worked inside this hour: the sum of its windows' tracked seconds.
   * Reported rather than derived from the number of windows, because a window
   * can hold a capture and only a couple of tracked minutes.
   */
  trackedSeconds: number;
  screenshotCount: number;
}

/**
 * The day's windows as hour rows, earliest first.
 *
 * Hours with nothing in them are not produced — the API already omits windows
 * with neither a capture nor measured activity, and inventing empty rows
 * between them would only ask the viewer to scroll past untracked time.
 */
export const groupWindowsByHour = (windows: ScreenshotTimelineWindow[]): HourBlock[] => {
  const blocks = new Map<string, HourBlock>();

  for (const window of [...windows].sort((a, b) => a.window_start.localeCompare(b.window_start))) {
    const { key, hour } = istHourParts(window.window_start);
    const block = blocks.get(key) ?? {
      key,
      startLabel: hourLabel(hour),
      endLabel: hourLabel((hour + 1) % 24),
      windows: [],
      trackedSeconds: 0,
      screenshotCount: 0,
    };
    block.windows.push(window);
    block.trackedSeconds += window.tracked_seconds ?? 0;
    block.screenshotCount += window.screenshot_count;
    blocks.set(key, block);
  }

  return [...blocks.values()].sort((a, b) => a.key.localeCompare(b.key));
};

/**
 * A duration in the words the activity caption uses — "4 minutes", "42
 * seconds". Rounded to whole minutes above a minute, because the denominator
 * of an activity figure is a rough scale, not a stopwatch reading.
 */
export const describeDuration = (seconds: number): string => {
  if (seconds < 60) return `${seconds} second${seconds === 1 ? '' : 's'}`;
  const minutes = Math.round(seconds / 60);
  return `${minutes} minute${minutes === 1 ? '' : 's'}`;
};
