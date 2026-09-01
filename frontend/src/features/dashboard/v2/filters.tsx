import React, { useEffect, useMemo, useRef, useState } from "react";
import { MONTHS, monthByKey, TODAY } from "./mockData";
import type { Member } from "../../../store/api/membersApi";
import type { Project } from "../../../store/api/projectsApi";
import { brandGradient } from "./theme";

/* ------------------------------------------------------------------ */
/* Dropdown shell — click-outside handling shared by every filter      */
/* ------------------------------------------------------------------ */

const useClickOutside = (onClose: () => void, active: boolean) => {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!active) return;
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [active, onClose]);
  return ref;
};

/* ------------------------------------------------------------------ */
/* Generic multi-select                                                */
/* ------------------------------------------------------------------ */

export interface Option {
  id: string;
  label: string;
  sub?: string;
}

export const MultiSelect: React.FC<{
  options: Option[];
  selected: string[];
  onChange: (ids: string[]) => void;
  allLabel: string;
  noun: string;
  icon?: React.ReactNode;
  compact?: boolean;
}> = ({ options, selected, onChange, allLabel, noun, icon, compact = false }) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useClickOutside(() => setOpen(false), open);

  const filtered = useMemo(
    () => options.filter((o) => (o.label || "").toLowerCase().includes(query.trim().toLowerCase())),
    [options, query]
  );

  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);

  const label =
    selected.length === 0
      ? allLabel
      : selected.length === 1
        ? (options.find((o) => o.id === selected[0])?.label ?? `1 ${noun}`)
        : `${selected.length} ${noun}s`;

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={
          "flex items-center gap-2 rounded-lg border bg-white font-semibold transition " +
          (selected.length > 0
            ? "border-[#2563EB]/40 text-[#2563EB]"
            : "border-[#E2E8F0] text-[#0F172A] hover:border-[#CBD5E1]") +
          (compact ? " px-3 py-1.5 text-xs" : " px-3.5 py-2 text-[13px]")
        }
      >
        {icon}
        <span className="max-w-[140px] truncate">{label}</span>
        {selected.length > 1 && (
          <span className="rounded bg-[#2563EB] px-1.5 text-[10px] font-bold text-white">{selected.length}</span>
        )}
        <svg className="h-3.5 w-3.5 text-[#94A3B8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-72 overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-xl">
          <div className="border-b border-[#F1F5F9] p-2.5">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Search ${noun}s...`}
              className="w-full rounded-lg bg-[#F8FAFC] px-3 py-2 text-[13px] text-[#0F172A] outline-none placeholder:text-[#94A3B8] focus:ring-2 focus:ring-[#2563EB]/25"
            />
          </div>

          <div className="flex items-center justify-between border-b border-[#F1F5F9] px-3 py-2">
            <button
              onClick={() => onChange(options.map((o) => o.id))}
              className="text-[11px] font-bold uppercase tracking-wider text-[#2563EB] hover:underline"
            >
              Select all
            </button>
            <span className="text-[11px] text-[#94A3B8]">
              {selected.length} / {options.length}
            </span>
            <button
              onClick={() => onChange([])}
              className="text-[11px] font-bold uppercase tracking-wider text-[#64748B] hover:underline"
            >
              Clear
            </button>
          </div>

          <ul className="max-h-64 overflow-y-auto p-1.5">
            {filtered.length === 0 && (
              <li className="px-3 py-6 text-center text-[12px] text-[#94A3B8]">No {noun}s match.</li>
            )}
            {filtered.map((o) => {
              const checked = selected.includes(o.id);
              return (
                <li key={o.id}>
                  <button
                    onClick={() => toggle(o.id)}
                    className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition hover:bg-[#F8FAFC]"
                  >
                    <span
                      className={
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition " +
                        (checked ? "border-[#2563EB] bg-[#2563EB]" : "border-[#CBD5E1] bg-white")
                      }
                    >
                      {checked && (
                        <svg className="h-3 w-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3.5" d="M5 13l4 4L19 6" />
                        </svg>
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-semibold text-[#0F172A]">{o.label}</span>
                      {o.sub && <span className="block truncate text-[11px] text-[#94A3B8]">{o.sub}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
};

const ProjectIcon = (
  <svg className="h-4 w-4 text-[#64748B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2z"
    />
  </svg>
);

export const MemberMultiSelect: React.FC<{
  members: Member[];
  selected: string[];
  onChange: (ids: string[]) => void;
}> = ({ members, selected, onChange }) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useClickOutside(() => setOpen(false), open);

  const selectedMembers = (members || []).filter((m) => selected.includes(String(m.id)));
  const filteredOptions = (members || []).filter((m) => (m.name || "").toLowerCase().includes(query.toLowerCase()));

  const getColor = (id: number) => {
    const colors = ['bg-blue-500', 'bg-rose-500', 'bg-emerald-500', 'bg-amber-500', 'bg-purple-500', 'bg-cyan-500'];
    return colors[id % colors.length];
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={
          "flex h-9 items-center gap-2 rounded-lg border bg-white px-3 text-[13px] font-semibold transition " +
          (open ? "border-[#38BDF8] ring-2 ring-[#38BDF8]/20" : "border-[#E2E8F0] hover:border-[#CBD5E1]")
        }
      >
        {selectedMembers.length === 0 ? (
          <>
            <svg className="h-4 w-4 text-[#94A3B8]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            <span className="text-[#0F172A]">All members</span>
          </>
        ) : (
          <div className="flex -space-x-2 items-center p-0.5">
            {selectedMembers.slice(0, 3).map(m => (
              <div 
                key={m.id} 
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-2 ring-white text-white text-[9px] font-bold shadow-sm ${getColor(m.id)}`}
                title={m.name}
              >
                {(m.name || 'U').split(' ').map((n: string) => n[0]).join('').substring(0, 2).toUpperCase()}
              </div>
            ))}
            {selectedMembers.length > 3 && (
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-2 ring-white bg-slate-100 text-slate-500 text-[9px] font-bold shadow-sm">
                +{selectedMembers.length - 3}
              </div>
            )}
          </div>
        )}
        <svg className="h-3.5 w-3.5 text-[#94A3B8]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
      </button>

      {open && (
        <div className="absolute right-0 lg:left-0 top-full z-40 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-2xl">
          <div className="mb-2 px-1 text-[11px] font-black uppercase tracking-wider text-slate-500">MEMBERS</div>
          <div className="mb-3 px-1">
            <input 
              type="text" 
              placeholder="Search members..." 
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 outline-none transition focus:border-blue-500 focus:bg-white"
            />
          </div>
          <div className="max-h-60 overflow-y-auto custom-scrollbar pr-1">
            {filteredOptions.length > 0 ? filteredOptions.map(emp => {
              const isSelected = selected.includes(String(emp.id));
              return (
                <label key={emp.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg p-2 hover:bg-slate-50 transition">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`shrink-0 flex h-8 w-8 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-sm ${getColor(emp.id)}`}>
                      {(emp.name || 'U').split(' ').map((n: string) => n[0]).join('').substring(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex flex-col">
                      <span className="truncate text-sm font-bold text-slate-700">{emp.name}</span>
                      <span className="truncate text-[10px] font-semibold text-slate-400">{emp.role}</span>
                    </div>
                  </div>
                  <div className="shrink-0 flex items-center justify-center">
                    <input 
                      type="checkbox" 
                      checked={isSelected}
                      onChange={(e) => {
                        if (e.target.checked) onChange([...selected, String(emp.id)]);
                        else onChange(selected.filter(id => id !== String(emp.id)));
                      }}
                      className="h-4 w-4 rounded border-slate-300 text-blue-500 focus:ring-blue-500" 
                    />
                  </div>
                </label>
              );
            }) : (
              <div className="py-4 text-center text-xs text-slate-500">No members found.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const ProjectMultiSelect: React.FC<{
  projects: Project[];
  selected: string[];
  onChange: (ids: string[]) => void;
  compact?: boolean;
}> = ({ projects, selected, onChange, compact }) => (
  <MultiSelect
    options={(projects || []).map((p) => ({ id: String(p.id), label: p.project_name }))}
    selected={selected}
    onChange={onChange}
    allLabel="All projects"
    noun="project"
    icon={ProjectIcon}
    compact={compact}
  />
);

/* ------------------------------------------------------------------ */
/* Month select                                                        */
/* ------------------------------------------------------------------ */

export const MonthSelect: React.FC<{
  value: string;
  onChange: (key: string) => void;
  compact?: boolean;
}> = ({ value, onChange, compact = false }) => {
  const [open, setOpen] = useState(false);
  const wrapRef = useClickOutside(() => setOpen(false), open);
  const current = monthByKey(value);

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={
          "flex items-center gap-2 rounded-lg font-bold text-white shadow-sm transition hover:opacity-90 " +
          (compact ? "px-3 py-1.5 text-xs" : "px-3.5 py-2 text-[13px]")
        }
        style={{ background: brandGradient }}
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <span>{current.label}</span>
        <svg className="h-3.5 w-3.5 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-56 overflow-hidden rounded-xl border border-[#E2E8F0] bg-white p-1.5 shadow-xl">
          <ul className="max-h-72 overflow-y-auto">
            {MONTHS.map((m) => (
              <li key={m.key}>
                <button
                  onClick={() => {
                    onChange(m.key);
                    setOpen(false);
                  }}
                  className={
                    "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[13px] font-semibold transition " +
                    (m.key === value ? "bg-[#2563EB]/10 text-[#2563EB]" : "text-[#0F172A] hover:bg-[#F8FAFC]")
                  }
                >
                  <span>{m.label}</span>
                  {m.key === MONTHS[0].key && (
                    <span className="rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#64748B]">
                      Current
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Date range filter — dual-calendar picker with preset rail           */
/* ------------------------------------------------------------------ */

export type RangePreset =
  | "today"
  | "yesterday"
  | "7d"
  | "lastWeek"
  | "2w"
  | "30d"
  | "month"
  | "lastMonth"
  | "custom";

export interface DateRange {
  preset: RangePreset;
  from: string;
  to: string;
}

export const PRESETS: { id: RangePreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "yesterday", label: "Yesterday" },
  { id: "7d", label: "Last 7 days" },
  { id: "lastWeek", label: "Last week" },
  { id: "2w", label: "Last 2 weeks" },
  { id: "month", label: "This month" },
  { id: "lastMonth", label: "Last month" },
];

const isoOf = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const parseIso = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
};

const shift = (days: number) => {
  const d = new Date(TODAY);
  d.setDate(d.getDate() - days);
  return isoOf(d);
};

const addDays = (d: Date, days: number) => {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + days);
  return copy;
};

/** Monday-based start of the week containing `d`. */
const startOfWeek = (d: Date) => addDays(d, -((d.getDay() + 6) % 7));

export const rangeFor = (preset: RangePreset, current: DateRange): DateRange => {
  const y = TODAY.getFullYear();
  const m = TODAY.getMonth();
  switch (preset) {
    case "today":
      return { preset, from: shift(0), to: shift(0) };
    case "yesterday":
      return { preset, from: shift(1), to: shift(1) };
    case "7d":
      return { preset, from: shift(6), to: shift(0) };
    case "lastWeek": {
      const lastMonday = addDays(startOfWeek(TODAY), -7);
      return { preset, from: isoOf(lastMonday), to: isoOf(addDays(lastMonday, 6)) };
    }
    case "2w":
      return { preset, from: shift(13), to: shift(0) };
    case "30d":
      return { preset, from: shift(29), to: shift(0) };
    case "month":
      return { preset, from: isoOf(new Date(y, m, 1)), to: shift(0) };
    case "lastMonth":
      return { preset, from: isoOf(new Date(y, m - 1, 1)), to: isoOf(new Date(y, m, 0)) };
    default:
      return { ...current, preset: "custom" };
  }
};

/** The preset a hand-picked span happens to match, so the rail stays in sync. */
const presetOf = (from: string, to: string): RangePreset => {
  const blank: DateRange = { preset: "custom", from, to };
  const hit = PRESETS.find((p) => {
    const r = rangeFor(p.id, blank);
    return r.from === from && r.to === to;
  });
  return hit ? hit.id : "custom";
};

/** The full span of a calendar month — used when a report is opened from the dashboard. */
export const rangeForMonth = (monthKey: string): DateRange => {
  const m = monthByKey(monthKey);
  return { preset: presetOf(m.from, m.to), from: m.from, to: m.to };
};

export const DEFAULT_RANGE: DateRange = rangeFor("30d", { preset: "30d", from: "", to: "" });

const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const longDate = (iso: string) =>
  iso
    ? parseIso(iso).toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "Pick a date";

/** Six Monday-first weeks covering the given month. */
const monthGrid = (year: number, month: number) => {
  const first = new Date(year, month, 1);
  const start = addDays(first, -((first.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, i) => addDays(start, i));
};

const CalendarPane: React.FC<{
  year: number;
  month: number;
  from: string;
  to: string;
  onPick: (iso: string) => void;
  onHover: (iso: string | null) => void;
  onPrev?: () => void;
  onNext?: () => void;
}> = ({ year, month, from, to, onPick, onHover, onPrev, onNext }) => {
  const todayIso = isoOf(TODAY);

  return (
    <div className="w-[248px]">
      <div className="mb-1 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrev}
          className={
            "flex h-6 w-6 items-center justify-center rounded text-[#94A3B8] transition hover:bg-[#F1F5F9] hover:text-[#0F172A] " +
            (onPrev ? "" : "invisible")
          }
          aria-label="Previous month"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="text-[15px] font-semibold">
          <span className="text-[#38BDF8]">{MONTH_NAMES[month]}</span>{" "}
          <span className="text-[#94A3B8]">{year}</span>
        </div>
        <button
          type="button"
          onClick={onNext}
          className={
            "flex h-6 w-6 items-center justify-center rounded text-[#94A3B8] transition hover:bg-[#F1F5F9] hover:text-[#0F172A] " +
            (onNext ? "" : "invisible")
          }
          aria-label="Next month"
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
        {monthGrid(year, month).map((date) => {
          const iso = isoOf(date);
          const outside = date.getMonth() !== month;
          const isStart = !!from && iso === from;
          const isEnd = !!to && iso === to;
          const spans = !!from && !!to && from !== to;
          const inRange = spans && iso > from && iso < to;

          return (
            <div
              key={iso}
              className={
                "flex justify-center py-0.5 " +
                (inRange || (spans && (isStart || isEnd)) ? "bg-[#38BDF8]/10 " : "") +
                (spans && isStart ? "rounded-l-full " : "") +
                (spans && isEnd ? "rounded-r-full " : "")
              }
            >
              <button
                type="button"
                onClick={() => onPick(iso)}
                onMouseEnter={() => onHover(iso)}
                onMouseLeave={() => onHover(null)}
                className={
                  "flex h-8 w-8 items-center justify-center rounded-full text-[13px] transition " +
                  (isStart || isEnd
                    ? "bg-[#38BDF8] font-bold text-white"
                    : outside
                      ? "text-[#CBD5E1] hover:bg-[#F1F5F9]"
                      : "text-[#0F172A] hover:bg-[#F1F5F9]") +
                  (iso === todayIso && !isStart && !isEnd ? " ring-1 ring-inset ring-[#38BDF8]/50" : "")
                }
              >
                {date.getDate()}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const DateRangeFilter: React.FC<{ value: DateRange; onChange: (r: DateRange) => void }> = ({
  value,
  onChange,
}) => {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState(() => {
    const d = value.from ? parseIso(value.from) : TODAY;
    return { year: d.getFullYear(), month: d.getMonth() };
  });

  const close = () => {
    setOpen(false);
    setAnchor(null);
    setHover(null);
  };
  const wrapRef = useClickOutside(close, open);

  const openPicker = () => {
    const d = value.from ? parseIso(value.from) : TODAY;
    setView({ year: d.getFullYear(), month: d.getMonth() });
    setAnchor(null);
    setHover(null);
    setOpen(true);
  };

  // While an anchor is down the calendar previews the span under the cursor.
  const preview = useMemo(() => {
    if (!anchor) return { from: value.from, to: value.to };
    const other = hover ?? anchor;
    return anchor <= other ? { from: anchor, to: other } : { from: other, to: anchor };
  }, [anchor, hover, value.from, value.to]);

  const pick = (iso: string) => {
    if (!anchor) {
      setAnchor(iso);
      return;
    }
    const [from, to] = anchor <= iso ? [anchor, iso] : [iso, anchor];
    onChange({ preset: presetOf(from, to), from, to });
    close();
  };

  const step = (delta: number) =>
    setView((v) => {
      const d = new Date(v.year, v.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });

  const right = new Date(view.year, view.month + 1, 1);

  return (
    <div className="relative flex items-center gap-3" ref={wrapRef}>
      <button
        type="button"
        onClick={() => (open ? close() : openPicker())}
        className={
          "flex items-center gap-3 rounded-lg border bg-white px-3.5 py-2 text-[13px] font-semibold text-[#0F172A] transition " +
          (open ? "border-[#38BDF8] ring-2 ring-[#38BDF8]/20" : "border-[#E2E8F0] hover:border-[#CBD5E1]")
        }
      >
        <span>
          {longDate(value.from)} - {longDate(value.to)}
        </span>
        <svg className="h-4 w-4 text-[#38BDF8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-40 mt-2 flex gap-5 rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-2xl">
          <div className="flex w-[132px] flex-col gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  onChange(rangeFor(p.id, value));
                  close();
                }}
                className={
                  "rounded-md border px-3 py-1.5 text-[13px] font-medium transition " +
                  (value.preset === p.id
                    ? "border-[#38BDF8] bg-[#38BDF8]/10 text-[#0284C7]"
                    : "border-[#E2E8F0] text-[#0F172A] hover:border-[#CBD5E1] hover:bg-[#F8FAFC]")
                }
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="flex gap-6">
            <CalendarPane
              year={view.year}
              month={view.month}
              from={preview.from}
              to={preview.to}
              onPick={pick}
              onHover={setHover}
              onPrev={() => step(-1)}
            />
            <CalendarPane
              year={right.getFullYear()}
              month={right.getMonth()}
              from={preview.from}
              to={preview.to}
              onPick={pick}
              onHover={setHover}
              onNext={() => step(1)}
            />
          </div>
        </div>
      )}
    </div>
  );
};
/* ------------------------------------------------------------------ */
/* CSV export                                                          */
/* ------------------------------------------------------------------ */

export const exportToCsv = (filename: string, headers: string[], rows: (string | number)[][]) => {
  const escape = (cell: string | number) => {
    const text = String(cell);
    return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  };
  const csv = [headers, ...rows].map((r) => r.map(escape).join(",")).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};
