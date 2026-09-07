import React, { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { FEEDBACK_CATEGORY_LABELS } from "../../store/api/feedbackApi";
import type { Feedback } from "../../store/api/feedbackApi";
import { formatISTDate } from "../../utils/duration";
import { CATEGORY_STYLES } from "./feedbackFilters";

/**
 * The feedback list, shared by the member and the organization-wide page.
 *
 * The two pages differ only in which endpoint fills this table and whether the
 * submitter is shown, so the markup lives in one place. `showEmployee` is off
 * on the member screen: a person reading their own submissions already knows
 * who sent them, and an id column there is noise, not information.
 *
 * Strictly read-only. Feedback carries no workflow -- no status, no assignee,
 * no reply -- so there is deliberately no row action anywhere on this screen.
 *
 * A wide table cannot shrink below its content, so on a narrow screen the rows
 * are rendered as stacked cards instead of being cut off.
 */

const columnHead =
  "px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-[#94A3B8]";

/** Up to two initials, matching the avatars the rest of the app draws. */
const initials = (name: string) =>
  (name || "?")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "?";

/**
 * A stable colour per person, so the same submitter looks the same on every
 * row without the backend having to store an avatar.
 */
const avatarHue = (name: string) => {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) hash = (hash * 31 + name.charCodeAt(i)) % 360;
  return hash;
};

/**
 * The category tag.
 *
 * Square-cornered rather than a lozenge: the tag sits in a column of a table
 * whose every other edge is square, and the pill shape fought that. The marker
 * beside the label is squared off for the same reason, and matches the one the
 * category dropdown draws so the filter and the column read as one control and
 * its result.
 */
const CategoryPill: React.FC<{ category: Feedback["category"] }> = ({ category }) => {
  const style = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.other;
  return (
    <span
      className="inline-flex items-center gap-2 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[11px] font-bold"
      style={{ color: style.text, backgroundColor: style.bg }}
    >
      <span className="h-2 w-2 rounded-[2px]" style={{ background: style.dot }} />
      {FEEDBACK_CATEGORY_LABELS[category] ?? category}
    </span>
  );
};

/**
 * A description cell: one line, ellipsised, with the full text on hover.
 *
 * Messages run to 5000 characters and need not contain a space, and the column
 * used to render them in full. One 1500-character word therefore set the
 * table's width, pushing the Submitted column off the side and leaving the
 * whole grid on a horizontal scrollbar -- every other row paid for that one.
 *
 * The tooltip is rendered into `document.body` rather than beside the cell.
 * The table scrolls horizontally, and a scroll container clips on *both* axes,
 * so a tooltip positioned inside it would be cut off by the very row it
 * belongs to.
 */
const DescriptionCell: React.FC<{ message: string }> = ({ message }) => {
  const textRef = useRef<HTMLDivElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);
  const hideTimer = useRef<number | null>(null);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const [placed, setPlaced] = useState<{ top: number; left: number; scrollable: boolean } | null>(null);

  const cancelHide = () => {
    if (hideTimer.current !== null) {
      window.clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
  };

  const show = () => {
    const node = textRef.current;
    if (!node) return;
    // Nothing was cut off, so there is nothing a tooltip could add. The
    // pending-hide timer is deliberately left alone here: cancelling it before
    // this check would keep a neighbouring tooltip alive on the way past.
    if (node.scrollWidth <= node.clientWidth) return;
    cancelHide();
    setPlaced(null);
    setAnchor(node.getBoundingClientRect());
  };

  /**
   * Leaving the cell gives a moment's grace before the tooltip goes, so the
   * pointer can travel onto it -- a long message is scrollable, and a tooltip
   * that vanished on the way there could not be read.
   */
  const scheduleHide = () => {
    cancelHide();
    hideTimer.current = window.setTimeout(() => {
      setAnchor(null);
      setPlaced(null);
    }, 120);
  };

  /**
   * Position the tooltip once its real size is known.
   *
   * A message runs to 5000 characters, which is taller than any window, so the
   * panel is capped and scrolls; where it goes depends on how tall it actually
   * ended up, not on a guess made before rendering. It is measured and placed
   * before the browser paints, and stays hidden until then, so it never
   * appears in the wrong spot for a frame.
   */
  useLayoutEffect(() => {
    if (!anchor || !tipRef.current) return;
    const tip = tipRef.current.getBoundingClientRect();
    const margin = 12;
    const below = anchor.bottom + 8;
    const top =
      below + tip.height <= window.innerHeight - margin
        ? below
        : Math.max(margin, Math.min(anchor.top - 8 - tip.height, window.innerHeight - tip.height - margin));
    const left = Math.max(margin, Math.min(anchor.left, window.innerWidth - tip.width - margin));
    // Only a message too long for the cap needs to be reachable by the
    // pointer. Every other tooltip stays click-through, so it never blocks the
    // rows it happens to cover.
    setPlaced({ top, left, scrollable: tipRef.current.scrollHeight > tipRef.current.clientHeight });
  }, [anchor]);

  return (
    <>
      <div
        ref={textRef}
        onMouseEnter={show}
        onMouseLeave={scheduleHide}
        onFocus={show}
        onBlur={scheduleHide}
        tabIndex={0}
        className="truncate rounded outline-none focus-visible:ring-2 focus-visible:ring-[#38BDF8]/40"
      >
        {message}
      </div>

      {anchor &&
        createPortal(
          <div
            ref={tipRef}
            role="tooltip"
            onMouseEnter={cancelHide}
            onMouseLeave={scheduleHide}
            style={{
              position: "fixed",
              top: placed?.top ?? anchor.bottom + 8,
              left: placed?.left ?? anchor.left,
              visibility: placed ? "visible" : "hidden",
              pointerEvents: placed?.scrollable ? "auto" : "none",
            }}
            className="z-[60] max-h-[min(320px,60vh)] max-w-[380px] overflow-y-auto overscroll-contain whitespace-pre-wrap break-words rounded-lg bg-[#0F172A] px-3 py-2 text-[12px] leading-5 text-white shadow-xl"
          >
            {message}
          </div>,
          document.body,
        )}
    </>
  );
};

const Submitter: React.FC<{ item: Feedback }> = ({ item }) => {
  const hue = avatarHue(item.employee_name || "");
  return (
    <div className="flex items-center gap-3">
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
        style={{ background: `hsl(${hue} 70% 94%)`, color: `hsl(${hue} 55% 32%)` }}
        aria-hidden="true"
      >
        {initials(item.employee_name)}
      </span>
      <div className="min-w-0">
        <div className="truncate text-[13px] font-bold text-[#0F172A]">{item.employee_name}</div>
        <div className="text-[11px] font-semibold text-[#94A3B8]">ID {item.employee_id}</div>
      </div>
    </div>
  );
};

export const FeedbackTable: React.FC<{ items: Feedback[]; showEmployee?: boolean }> = ({
  items,
  showEmployee = true,
}) => (
  <>
    {/* Table — from `md` up */}
    <div className="hidden overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-sm md:block">
      <div className="overflow-x-auto">
        {/*
          `table-fixed` is what makes the truncation possible: under the default
          `auto` layout a cell grows to fit its content and `max-width` on a
          `<td>` is ignored, so no amount of ellipsis styling would have held
          the description column still.
        */}
        <table className="w-full min-w-[640px] table-fixed border-collapse">
          <colgroup>
            {showEmployee && <col style={{ width: 250 }} />}
            <col style={{ width: 190 }} />
            <col />
            <col style={{ width: 130 }} />
          </colgroup>
          <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
            <tr>
              {showEmployee && <th className={columnHead}>Employee</th>}
              <th className={columnHead}>Category</th>
              <th className={columnHead}>{showEmployee ? "Description" : "Reason"}</th>
              <th className={`${columnHead} text-right`}>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={item.id}
                className="border-b border-[#F1F5F9] transition-colors last:border-0 hover:bg-[#F8FAFC]"
              >
                {showEmployee && (
                  <td className="px-5 py-3.5">
                    <Submitter item={item} />
                  </td>
                )}
                <td className="px-5 py-3.5 align-top">
                  <CategoryPill category={item.category} />
                </td>
                <td className="px-5 py-3.5 align-top text-[13px] leading-5 text-[#334155]">
                  <DescriptionCell message={item.message} />
                </td>
                <td className="whitespace-nowrap px-5 py-3.5 text-right align-top text-[12px] font-semibold text-[#64748B]">
                  {formatISTDate(item.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {/* Stacked cards — below `md` */}
    <div className="space-y-3 md:hidden">
      {items.map((item) => (
        <div key={item.id} className="rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <CategoryPill category={item.category} />
            <span className="shrink-0 text-[12px] font-semibold text-[#64748B]">
              {formatISTDate(item.created_at)}
            </span>
          </div>
          {showEmployee && (
            <div className="mt-3">
              <Submitter item={item} />
            </div>
          )}
          <p className="mt-3 whitespace-pre-wrap break-words text-[13px] leading-5 text-[#334155]">
            {item.message}
          </p>
        </div>
      ))}
    </div>
  </>
);
