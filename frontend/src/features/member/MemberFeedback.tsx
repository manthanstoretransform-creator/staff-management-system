import React, { useState } from "react";
import { MemberShell } from "./MemberShell";
import { Card, EmptyState, ErrorNote, Spinner } from "./MemberUi";
import { FeedbackTable } from "../feedback/FeedbackTable";
import { useGetMyFeedbackQuery } from "../../store/api/feedbackApi";
import { InlineRefreshIndicator } from "../../components/InlineRefreshIndicator";
import { PaginationArrow } from "../../components/PaginationArrow";

/**
 * The member's own feedback.
 *
 * `/feedback/my` already answers with only the caller's submissions — the owner
 * comes from the access token, not from anything this page sends — so nothing
 * is filtered client-side and another person's message can never reach here.
 * Read-only: feedback is submitted from the Monitra desktop client.
 */

const PAGE_SIZE = 20;

export const MemberFeedback: React.FC = () => {
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, isError } = useGetMyFeedbackQuery({
    page,
    limit: PAGE_SIZE,
  });

  const items = data?.items ?? [];
  const totalPages = data?.pages ?? 0;

  return (
    <MemberShell
      title="Feedback"
      subtitle="Every Feedback & Help message you have submitted from the desktop app."
      actions={<InlineRefreshIndicator active={isFetching && !isLoading} />}
    >
      <div className="w-full space-y-6 pb-20">
        {isError && <ErrorNote message="Your feedback could not be loaded. Please try again." />}

        {isLoading ? (
          <Spinner label="Loading your feedback…" />
        ) : items.length === 0 ? (
          <Card>
            <EmptyState
              message="No feedback submitted yet."
              hint="Send feedback from the Monitra desktop app and it will appear here."
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
    </MemberShell>
  );
};
