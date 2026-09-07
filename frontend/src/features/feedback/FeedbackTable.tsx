import React from "react";
import { FEEDBACK_CATEGORY_LABELS } from "../../store/api/feedbackApi";
import type { Feedback } from "../../store/api/feedbackApi";
import { formatISTDate } from "../../utils/duration";

/**
 * The feedback list, shared by the member and the organization-wide page.
 *
 * The two pages differ only in which endpoint fills this table, so the markup
 * lives in one place. It is strictly read-only: there is no row action, no
 * status column and no control of any kind, because feedback carries no
 * workflow — it is submitted from the desktop client and read here.
 *
 * A wide table cannot shrink below its content, so on a narrow screen the rows
 * are rendered as stacked cards instead of being cut off.
 */

const columnHead =
  "px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-[#94A3B8]";

const CategoryPill: React.FC<{ category: Feedback["category"] }> = ({ category }) => (
  <span className="inline-flex items-center whitespace-nowrap rounded-full bg-[#EFF6FF] px-2.5 py-1 text-[11px] font-bold text-[#2563EB]">
    {FEEDBACK_CATEGORY_LABELS[category] ?? category}
  </span>
);

export const FeedbackTable: React.FC<{ items: Feedback[]; showEmployee?: boolean }> = ({
  items,
  showEmployee = true,
}) => (
  <>
    {/* Table — from `md` up */}
    <div className="hidden overflow-x-auto rounded-xl border border-[#E2E8F0] bg-white shadow-sm md:block">
      <table className="w-full min-w-[720px] border-collapse">
        <thead className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
          <tr>
            {showEmployee && (
              <>
                <th className={columnHead}>Employee ID</th>
                <th className={columnHead}>Employee Name</th>
              </>
            )}
            <th className={columnHead}>Category</th>
            <th className={columnHead}>Description</th>
            <th className={columnHead}>Submitted</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b border-[#F1F5F9] last:border-0 hover:bg-[#F8FAFC]">
              {showEmployee && (
                <>
                  <td className="px-4 py-3 text-[13px] font-semibold text-[#64748B]">
                    {item.employee_id}
                  </td>
                  <td className="px-4 py-3 text-[13px] font-bold text-[#0F172A]">
                    {item.employee_name}
                  </td>
                </>
              )}
              <td className="px-4 py-3">
                <CategoryPill category={item.category} />
              </td>
              <td className="max-w-[420px] whitespace-pre-wrap px-4 py-3 text-[13px] leading-5 text-[#334155]">
                {item.message}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-[13px] font-semibold text-[#64748B]">
                {formatISTDate(item.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
            <div className="mt-3 text-[13px] font-bold text-[#0F172A]">
              {item.employee_name}
              <span className="ml-2 text-[12px] font-semibold text-[#94A3B8]">
                #{item.employee_id}
              </span>
            </div>
          )}
          <p className="mt-2 whitespace-pre-wrap text-[13px] leading-5 text-[#334155]">
            {item.message}
          </p>
        </div>
      ))}
    </div>
  </>
);
