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

/** The largest page the backend will serve; see the `limit` bound on both routes. */
const MAX_PAGE_SIZE = 100;

/**
 * Read every page of a feedback list and return the rows as one array.
 *
 * The Feedback screens filter by search term, date range and submitter, and the
 * API offers none of those -- `page`, `limit` and `category` are the only
 * parameters either route takes. Filtering one server page client-side would
 * silently answer "no results" for a match sitting on page two, so the whole
 * set is loaded once and filtered here instead. This mirrors `getAllProjects`
 * in `projectsApi`, which pages the same way for the same reason.
 *
 * Page one is fetched first because only it can say how many pages there are;
 * the rest go out together rather than in series.
 */
const fetchEveryPage = async (
  base: string,
  baseQuery: (arg: string) => Promise<{ data?: unknown; error?: unknown }>,
) => {
  const first = await baseQuery(`${base}?page=1&limit=${MAX_PAGE_SIZE}`);
  if (first.error) return { error: first.error as never };

  const firstPage = first.data as FeedbackListResponse;
  const totalPages = firstPage.pages || 1;
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, totalPages - 1) }, (_, index) =>
      baseQuery(`${base}?page=${index + 2}&limit=${MAX_PAGE_SIZE}`),
    ),
  );

  const items = [...firstPage.items];
  for (const page of rest) {
    // One failed page must not be reported as a short list -- a filter would
    // then be applied to rows the user cannot see are missing.
    if (page.error) return { error: page.error as never };
    items.push(...(page.data as FeedbackListResponse).items);
  }
  return { data: items };
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

    /** Every feedback the caller may read, unpaginated, for client-side filtering. */
    getAllFeedbackItems: builder.query<Feedback[], void>({
      queryFn: (_arg, _api, _extraOptions, baseQuery) =>
        fetchEveryPage(ENDPOINTS.FEEDBACK.BASE, baseQuery as never) as never,
      providesTags: [{ type: 'Feedback' as const, id: 'ALL' }],
    }),

    /** Everything the caller submitted, unpaginated, for client-side filtering. */
    getMyFeedbackItems: builder.query<Feedback[], void>({
      queryFn: (_arg, _api, _extraOptions, baseQuery) =>
        fetchEveryPage(ENDPOINTS.FEEDBACK.MY, baseQuery as never) as never,
      providesTags: [{ type: 'Feedback' as const, id: 'MINE' }],
    }),
  }),
});

export const {
  useGetMyFeedbackQuery,
  useGetAllFeedbackQuery,
  useGetAllFeedbackItemsQuery,
  useGetMyFeedbackItemsQuery,
} = feedbackApi;
