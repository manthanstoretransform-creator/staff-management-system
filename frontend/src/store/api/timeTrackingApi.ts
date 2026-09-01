import { baseApi } from './baseApi';
import { ENDPOINTS } from '../../api/endpoints';

export interface TimeTrackingEntry {
  employee_id: number;
  name: string;
  email: string;
  designation: string;
  date: string;
  start_time: string | null;
  end_time: string | null;
  total_seconds: number;
  /** Legacy "13h 22m" label. Prefer total_time for exact durations. */
  total_hours: string;
  /** Exact tracked duration, HH:MM:SS. */
  total_time: string;
}

export interface TimeTrackingListResponse {
  items: TimeTrackingEntry[];
  pagination: { page?: number; limit?: number; total?: number; total_pages?: number; [key: string]: unknown };
}

export interface TimeTrackingStatus {
  id: number;
  name: string;
  color: string;
}

export interface TimeTrackingTask {
  id: number;
  name: string;
  status: TimeTrackingStatus;
  total_seconds: number;
  total_hours: string;
  total_time: string;
}

export interface TimeTrackingProject {
  id: number;
  name: string;
  status: TimeTrackingStatus;
  total_seconds: number;
  total_hours: string;
  total_time: string;
  tasks: TimeTrackingTask[];
}

export interface TimeTrackingDetails {
  employee: { id: number; name: string; email: string; designation: string; role: string };
  start_date: string;
  end_date: string;
  summary: { start_time: string | null; end_time: string | null; total_seconds: number; total_hours: string; total_time: string };
  projects: TimeTrackingProject[];
}

const addDateParams = (url: string, params: { range?: string; date?: string; start_date?: string; end_date?: string; employee_id?: number }) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value));
  });
  const queryString = query.toString();
  return queryString ? `${url}?${queryString}` : url;
};

export const timeTrackingApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getTimeTracking: builder.query<TimeTrackingListResponse, { range?: string; date?: string; start_date?: string; end_date?: string; employee_id?: number; page?: number; limit?: number }>({
      query: (params) => addDateParams(ENDPOINTS.TIME_TRACKING.GET_ALL, params),
      providesTags: [{ type: 'TimeTracking' as const, id: 'LIST' }],
    }),
    getTimeTrackingDetails: builder.query<TimeTrackingDetails, { employeeId: number; range?: string; date?: string; start_date?: string; end_date?: string }>({
      query: ({ employeeId, ...params }) => addDateParams(ENDPOINTS.TIME_TRACKING.GET_BY_EMPLOYEE(employeeId), params),
      providesTags: (_result, _error, { employeeId }) => [{ type: 'TimeTracking' as const, id: employeeId }],
    }),
  }),
});

export const { useGetTimeTrackingQuery, useGetTimeTrackingDetailsQuery } = timeTrackingApi;
