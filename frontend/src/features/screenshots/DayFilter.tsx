import React, { useEffect, useMemo, useRef, useState } from 'react';
import { IST_TIME_ZONE } from '../../utils/duration';

/**
 * The screenshots page's date control: one day at a time.
 *
 * The rest of the app filters by a *span*, through the dashboard's
 * `DateRangeFilter`, and this screen used that too. It reads badly here for
 * two reasons. The grid is organised as hours of a single tracked day, so a
 * week of days is a page nobody scrolls to the bottom of; and the range picker
 * commits only on a *second* click — picking one day and getting no change is
 * what "the date filter doesn't work" turns out to mean. A day picker commits
 * on the first click and cannot leave the control in a half-chosen state.
 *
 * Every date here is an IST calendar date, matching what the API means by
 * `from`/`to`, so a viewer in another timezone still asks for the day the
 * employee worked.
 */

/** Today's IST calendar date as `YYYY-MM-DD`. */
export const istTodayIso = (): string =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: IST_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());

const parseIso = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
};

const isoOf = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const addDays = (iso: string, days: number) => {
  const d = parseIso(iso);
  d.setDate(d.getDate() + days);
  return isoOf(d);
};

const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

/** Six Monday-first weeks covering the given month. */
const monthGrid = (year: number, month: number) => {
  const first = new Date(year, month, 1);
  const start = new Date(first);
  start.setDate(start.getDate() - ((first.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
};

/** How the chosen day reads on the button, e.g. "Tue, 08 Sep 2026". */
const longDate = (iso: string) =>
  parseIso(iso).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

export const DayFilter: React.FC<{
  /** The selected IST day, `YYYY-MM-DD`. */
  value: string;
  onChange: (iso: string) => void;
}> = ({ value, onChange }) => {
  const today = useMemo(istTodayIso, []);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => {
    const d = parseIso(value);
    return { year: d.getFullYear(), month: d.getMonth() };
  });
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const atToday = value >= today;
  const pick = (iso: string) => {
    if (iso > today) return;
    onChange(iso);
    setOpen(false);
  };

  const step = (delta: number) =>
    setView((v) => {
      const d = new Date(v.year, v.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });

  // There is nothing to look at past today, so the calendar never opens on a
  // month made entirely of unselectable days.
  const atLatestMonth =
    view.year > parseIso(today).getFullYear() ||
    (view.year === parseIso(today).getFullYear() && view.month >= parseIso(today).getMonth());

  return (
    <div className="relative flex items-center gap-1" ref={wrapRef}>
      <button
        type="button"
        onClick={() => onChange(addDays(value, -1))}
        aria-label="Previous day"
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#E2E8F0] bg-white text-[#64748B] transition hover:border-[#CBD5E1] hover:text-[#0F172A]"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      <button
        type="button"
        onClick={() => {
          const d = parseIso(value);
          setView({ year: d.getFullYear(), month: d.getMonth() });
          setOpen((o) => !o);
        }}
        aria-expanded={open}
        className={
          'flex h-9 items-center gap-2 rounded-lg border bg-white px-3.5 text-[13px] font-semibold text-[#0F172A] transition ' +
          (open ? 'border-[#38BDF8] ring-2 ring-[#38BDF8]/20' : 'border-[#E2E8F0] hover:border-[#CBD5E1]')
        }
      >
        <svg className="h-4 w-4 text-[#38BDF8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <span>{longDate(value)}</span>
        {value === today && (
          <span className="rounded-full bg-[#38BDF8]/10 px-2 py-0.5 text-[10px] font-bold text-[#0284C7]">
            Today
          </span>
        )}
      </button>

      <button
        type="button"
        onClick={() => !atToday && onChange(addDays(value, 1))}
        disabled={atToday}
        aria-label="Next day"
        className={
          'flex h-9 w-9 items-center justify-center rounded-lg border border-[#E2E8F0] bg-white transition ' +
          (atToday
            ? 'cursor-not-allowed text-[#E2E8F0]'
            : 'text-[#64748B] hover:border-[#CBD5E1] hover:text-[#0F172A]')
        }
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {!atToday && (
        <button
          type="button"
          onClick={() => onChange(today)}
          className="ml-1 h-9 rounded-lg border border-[#E2E8F0] bg-white px-3 text-[12px] font-bold text-[#2563EB] transition hover:border-[#CBD5E1]"
        >
          Today
        </button>
      )}

      {open && (
        <div className="absolute left-0 top-full z-40 mt-2 w-[264px] rounded-xl border border-[#E2E8F0] bg-white p-3 shadow-2xl">
          <div className="mb-1 flex items-center justify-between">
            <button
              type="button"
              onClick={() => step(-1)}
              aria-label="Previous month"
              className="flex h-6 w-6 items-center justify-center rounded text-[#94A3B8] transition hover:bg-[#F1F5F9] hover:text-[#0F172A]"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="text-[15px] font-semibold">
              <span className="text-[#38BDF8]">{MONTH_NAMES[view.month]}</span>{' '}
              <span className="text-[#94A3B8]">{view.year}</span>
            </div>
            <button
              type="button"
              onClick={() => !atLatestMonth && step(1)}
              disabled={atLatestMonth}
              aria-label="Next month"
              className={
                'flex h-6 w-6 items-center justify-center rounded transition ' +
                (atLatestMonth
                  ? 'cursor-not-allowed text-[#E2E8F0]'
                  : 'text-[#94A3B8] hover:bg-[#F1F5F9] hover:text-[#0F172A]')
              }
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          <div className="grid grid-cols-7">
            {WEEKDAYS.map((d) => (
              <div key={d} className="py-2 text-center text-[12px] font-bold text-[#0F172A]">
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7">
            {monthGrid(view.year, view.month).map((date) => {
              const iso = isoOf(date);
              const outside = date.getMonth() !== view.month;
              // Tracked time only ever exists in the past.
              const future = iso > today;
              const selected = iso === value;

              return (
                <div key={iso} className="flex justify-center py-0.5">
                  <button
                    type="button"
                    disabled={future}
                    aria-disabled={future}
                    onClick={() => pick(iso)}
                    className={
                      'flex h-8 w-8 items-center justify-center rounded-full text-[13px] transition ' +
                      (future
                        ? 'cursor-not-allowed text-[#E2E8F0]'
                        : selected
                          ? 'bg-[#38BDF8] font-bold text-white'
                          : outside
                            ? 'text-[#CBD5E1] hover:bg-[#F1F5F9]'
                            : 'text-[#0F172A] hover:bg-[#F1F5F9]') +
                      (iso === today && !selected ? ' ring-1 ring-inset ring-[#38BDF8]/50' : '')
                    }
                  >
                    {date.getDate()}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
