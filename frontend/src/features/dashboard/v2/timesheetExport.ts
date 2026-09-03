import type { DetailedLogItem } from "../../../store/api/reportsApi";

/**
 * Builds the "timesheet" shape of the export: one row per
 * member x project x to-do, one column per calendar day in the range, and a
 * row total.
 *
 * The source is `/reports/detailed-logs`, which is the only endpoint that
 * returns tracked time at (date, member, project, task) grain. Every other
 * report endpoint has already collapsed one of those axes, so a pivot built
 * from them would have to guess how to split a total back across days — this
 * one never guesses.
 *
 * A day cell of `0:00:00` is a real measurement: the row existed in the range
 * and nothing was tracked against it that day. Cells are never blank, because
 * the grid is dense by construction — every row carries every day.
 */

/** Every calendar date from `from` to `to`, inclusive, as `YYYY-MM-DD`. */
export const datesInRange = (from: string, to: string): string[] => {
  const parse = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(Date.UTC(y, (m || 1) - 1, d || 1));
  };
  const isoOf = (date: Date) => date.toISOString().slice(0, 10);

  const start = parse(from);
  const end = parse(to);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return [];

  const dates: string[] = [];
  // A hard ceiling so a mistyped range cannot build a million-column sheet.
  for (let day = start; day <= end && dates.length < 400; day.setUTCDate(day.getUTCDate() + 1)) {
    dates.push(isoOf(day));
  }
  return dates;
};

/**
 * `H:MM:SS` with the hour left unpadded — the clock format the timesheet uses,
 * which is deliberately not `formatHMS`'s zero-padded `HH:MM:SS`.
 */
export const formatClock = (totalSeconds: number): string => {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};

export interface TimesheetRow {
  memberName: string;
  projectName: string;
  taskName: string;
  /** Date (`YYYY-MM-DD`) -> seconds tracked by this member on this to-do. */
  secondsByDate: Map<string, number>;
  totalSeconds: number;
}

/**
 * Collapses the log rows into one entry per member x project x to-do.
 *
 * Rows are keyed on ids where the API supplies them and on the displayed name
 * otherwise, so two genuinely different projects that happen to share a name
 * stay apart, while entries with no project or task still get one honest
 * bucket instead of being dropped.
 */
export const buildTimesheetRows = (logs: DetailedLogItem[]): TimesheetRow[] => {
  const rows = new Map<string, TimesheetRow>();

  logs.forEach((log) => {
    const projectName = log.project_name || "No project";
    const taskName = log.task_name || "No to-do";
    const key = [
      log.member_id,
      log.project_id ?? `name:${projectName}`,
      log.task_id ?? `name:${taskName}`,
    ].join("|");

    const row =
      rows.get(key) ??
      {
        memberName: log.member_name || "Unknown",
        projectName,
        taskName,
        secondsByDate: new Map<string, number>(),
        totalSeconds: 0,
      };

    const seconds = log.tracked_seconds || 0;
    // `date` is the IST calendar date the backend already bucketed the entry
    // into; re-deriving it here from a timestamp would risk a second answer.
    const date = String(log.date).slice(0, 10);
    row.secondsByDate.set(date, (row.secondsByDate.get(date) || 0) + seconds);
    row.totalSeconds += seconds;
    rows.set(key, row);
  });

  return [...rows.values()].sort(
    (a, b) =>
      a.memberName.localeCompare(b.memberName) ||
      a.projectName.localeCompare(b.projectName) ||
      a.taskName.localeCompare(b.taskName)
  );
};

/** Header row for the timesheet sheet, in file order. */
export const timesheetHeaders = (dates: string[]): string[] => [
  "Member",
  "Organization",
  "Time Zone",
  "Projects",
  "Task Summary",
  ...dates,
  "Total worked",
];

/** One CSV line per timesheet row, aligned to `dates`. */
export const timesheetBody = (
  rows: TimesheetRow[],
  dates: string[],
  organization: string,
  timeZone: string
): string[][] =>
  rows.map((row) => [
    row.memberName,
    organization,
    timeZone,
    row.projectName,
    row.taskName,
    ...dates.map((date) => formatClock(row.secondsByDate.get(date) || 0)),
    formatClock(row.totalSeconds),
  ]);
