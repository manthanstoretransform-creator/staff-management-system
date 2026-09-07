import { baseApi } from './baseApi';
import { ENDPOINTS } from '../../api/endpoints';

/**
 * Feedback & Help, read-only.
 *
 * Feedback is *submitted* from the Monitra desktop client; the dashboard shows
 * it and nothing else. There is deliberately no mutation endpoint here — no
 * approve, no status, no response — because the backend offers none.
 *
 * The two queries differ only in who they are allowed to read. `getMyFeedback`
 * takes no user id: the backend derives the owner from the access token, so
 * there is nothing a caller could change to see somebody else's messages.
 * `getAllFeedback` is answered only for Admin, HR and Leader and is scoped to
 * the caller's own organization.
 */

export type FeedbackCategory =
  | 'suggestion'
  | 'report_a_problem'
  | 'general_feedback'
  | 'need_help'
  | 'account_login_issue'
  | 'other';

export interface Feedback {
  id: number;
  employee_id: number;
  employee_name: string;
  category: FeedbackCategory;
  message: string;
  created_at: string;
  updated_at: string | null;
}

export interface FeedbackListResponse {
  items: Feedback[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export interface FeedbackListArgs {
  page?: number;
  limit?: number;
  category?: FeedbackCategory | null;
}

/** Wire values are snake_case; these are what the table shows. */
export const FEEDBACK_CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  suggestion: 'Suggestion',
  report_a_problem: 'Report a problem',
  general_feedback: 'General feedback',
  need_help: 'Need help',
  account_login_issue: 'Account / login issue',
  other: 'Other',
};

const listQuery = (base: string, params: FeedbackListArgs) => {
  const query = new URLSearchParams();
  query.set('page', String(params.page ?? 1));
  query.set('limit', String(params.limit ?? 20));
  if (params.category) query.set('category', params.category);
  return `${base}?${query.toString()}`;
};

export const feedbackApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getMyFeedback: builder.query<FeedbackListResponse, FeedbackListArgs>({
      query: (params) => listQuery(ENDPOINTS.FEEDBACK.MY, params),
      providesTags: [{ type: 'Feedback' as const, id: 'MINE' }],
    }),
    getAllFeedback: builder.query<FeedbackListResponse, FeedbackListArgs>({
      query: (params) => listQuery(ENDPOINTS.FEEDBACK.BASE, params),
      providesTags: [{ type: 'Feedback' as const, id: 'ALL' }],
    }),
  }),
});

export const { useGetMyFeedbackQuery, useGetAllFeedbackQuery } = feedbackApi;
