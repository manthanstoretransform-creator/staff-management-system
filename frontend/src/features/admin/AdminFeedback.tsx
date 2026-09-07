import React, { useState } from "react";
import { V2Shell } from "../dashboard/v2/V2Shell";
import { Card, EmptyState, ErrorNote, Spinner } from "../member/MemberUi";
import { FeedbackTable } from "../feedback/FeedbackTable";
import {
  FEEDBACK_CATEGORY_LABELS,
  useGetAllFeedbackQuery,
} from "../../store/api/feedbackApi";
import type { FeedbackCategory } from "../../store/api/feedbackApi";
import { InlineRefreshIndicator } from "../../components/InlineRefreshIndicator";
import { PaginationArrow } from "../../components/PaginationArrow";

/**
 * Every feedback filed in the organization, for Admin, HR and Leader.
 *
 * `GET /feedback` scopes the rows to the caller's own organization and refuses
 * any other role with a 403, so this page sends no organization id and does no
 * filtering of its own beyond the category the user picks. The list includes
 * the viewer's own submissions — an admin who sends feedback from the desktop
 * app sees it here alongside everyone else's.
 *
 * Strictly read-only. Feedback has no approval, no status and no response, so
 * there is deliberately no row action anywhere on this screen.
 *
 * The card/empty/spinner primitives come from the member UI kit rather than
 * being re-inlined here; they are plain presentational pieces and this page
 * needs exactly the states they already express.
 */

const PAGE_SIZE = 20;

const CATEGORIES = Object.keys(FEEDBACK_CATEGORY_LABELS) as FeedbackCategory[];

export const AdminFeedback: React.FC = () => {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<FeedbackCategory | null>(null);

  const { data, isLoading, isFetching, isError } = useGetAllFeedbackQuery({
    page,
    limit: PAGE_SIZE,
    category,
  });

  const items = data?.items ?? [];
  const totalPages = data?.pages ?? 0;

  const applyCategory = (next: FeedbackCategory | null) => {
    setCategory(next);
    setPage(1);
  };

  const chip = (active: boolean) =>
    "rounded-lg px-3 py-2 text-[12px] font-bold transition " +
    (active ? "bg-[#2563EB] text-white" : "text-[#64748B] hover:bg-[#F8FAFC]");

  return (
    <V2Shell
      title="Feedback"
      subtitle="Feedback & Help messages submitted by everyone in your organization."
      actions={<InlineRefreshIndicator active={isFetching && !isLoading} />}
    >
      <div className="w-full space-y-6 pb-20">
        <Card>
          <div className="flex flex-wrap items-center gap-1.5">
            <button onClick={() => applyCategory(null)} className={chip(category === null)}>
              All
            </button>
            {CATEGORIES.map((value) => (
              <button
                key={value}
                onClick={() => applyCategory(value)}
                className={chip(category === value)}
              >
                {FEEDBACK_CATEGORY_LABELS[value]}
              </button>
            ))}
          </div>
        </Card>

        {isError && <ErrorNote message="Feedback could not be loaded. Please try again." />}

        {isLoading ? (
          <Spinner label="Loading feedback…" />
        ) : items.length === 0 ? (
          <Card>
            <EmptyState
              message={
                category
                  ? "No feedback in this category."
                  : "No feedback submitted yet."
              }
              hint="Feedback appears here once someone sends it from the Monitra desktop app."
            />
          </Card>
        ) : (
          <div className={`transition-opacity ${isFetching ? "opacity-60" : ""}`}>
            <FeedbackTable items={items} />
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between rounded-xl border border-[#E2E8F0] bg-white px-4 py-3 shadow-sm">
            <span className="text-[12px] font-semibold text-[#64748B]">
              Page {data?.page} of {totalPages} · {data?.total} submissions
            </span>
            <div className="flex items-center gap-2">
              <PaginationArrow
                direction="prev"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              />
              <PaginationArrow
                direction="next"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              />
            </div>
          </div>
        )}
      </div>
    </V2Shell>
  );
};
