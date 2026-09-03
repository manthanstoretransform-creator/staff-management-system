import { baseApi } from './baseApi';
import { ENDPOINTS } from '../../api/endpoints';

export interface TimeEntryScreenshot {
  id: number;
  organization_id: number;
  time_entry_id: number;
  captured_at: string;
  /**
   * Wherever the capturing client stored the image. It is free text in the
   * schema, so it may be an absolute URL or a path on the machine that took
   * it — a screen showing these must handle both rather than assume a URL.
   */
  file_path: string;
  monitor_number: number;
  created_at: string;
}

export interface GetScreenshotsArgs {
  time_entry_id?: number;
  /**
   * Ignored for callers without `time_entries:view_all` — the service pins
   * them to their own captures regardless of what is sent.
   */
  user_id?: number;
  limit?: number;
}

export const screenshotsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getScreenshots: builder.query<TimeEntryScreenshot[], GetScreenshotsArgs>({
      query: (params) => {
        const query = new URLSearchParams();
        query.set('limit', String(params.limit ?? 200));
        if (params.time_entry_id) query.set('time_entry_id', String(params.time_entry_id));
        if (params.user_id) query.set('user_id', String(params.user_id));
        return `${ENDPOINTS.TIME_ENTRY_SCREENSHOTS.BASE}?${query.toString()}`;
      },
      providesTags: [{ type: 'TimeTracking' as const, id: 'SCREENSHOTS' }],
    }),
  }),
});

export const { useGetScreenshotsQuery } = screenshotsApi;
