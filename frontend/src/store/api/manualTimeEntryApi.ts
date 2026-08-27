import { baseApi } from './baseApi';
import { ENDPOINTS } from '../../api/endpoints';

/**
 * What `POST /manual-time-entries` accepts today. Note what is NOT here:
 *
 *  - no `user_id`  — the backend always records the entry against the caller
 *                    (`ManualTimeEntryService.create_manual_entry`), so an admin
 *                    cannot yet log time on another employee's behalf.
 *  - no start/end  — the backend derives them as midnight-UTC + `total_seconds`,
 *                    so the clock-in/clock-out the user types is not persisted.
 *
 * A replacement create endpoint is being written on the backend. When it lands,
 * this payload and the `body` below are the only things that need to change —
 * every caller goes through `useCreateManualTimeEntryMutation`.
 */
export interface ManualTimeEntryCreate {
  project_id: number;
  task_id: number;
  work_date: string;
  total_seconds: number;
  is_billable?: boolean;
  description?: string;
}

export interface ManualTimeEntryRead {
  id: number;
  organization_id: number;
  user_id: number;
  project_id: number;
  task_id: number;
  work_date: string;
  start_time: string;
  end_time: string;
  total_seconds: number;
  description: string | null;
  is_billable: boolean;
  approval_status: string;
  approved_by: number | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export const manualTimeEntryApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    createManualTimeEntry: builder.mutation<ManualTimeEntryRead, ManualTimeEntryCreate>({
      query: (body) => ({ url: ENDPOINTS.MANUAL_TIME_ENTRIES.BASE, method: 'POST', body }),
      // The Time Tracking screens aggregate time server-side, so there is no
      // safe local guess to patch in — mark them stale and let them refetch.
      invalidatesTags: [{ type: 'TimeTracking', id: 'LIST' }],
    }),
  }),
});

export const { useCreateManualTimeEntryMutation } = manualTimeEntryApi;
