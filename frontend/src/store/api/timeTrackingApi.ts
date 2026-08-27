import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
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
  total_hours: string;
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
}

export interface TimeTrackingProject {
  id: number;
  name: string;
  status: TimeTrackingStatus;
  total_seconds: number;
  total_hours: string;
  tasks: TimeTrackingTask[];
}

export interface TimeTrackingDetails {
  employee: { id: number; name: string; email: string; designation: string; role: string };
  start_date: string;
  end_date: string;
  summary: { start_time: string | null; end_time: string | null; total_seconds: number; total_hours: string };
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

export const timeTrackingApi = createApi({
  reducerPath: 'timeTrackingApi',
  keepUnusedDataFor: 300,
  baseQuery: fetchBaseQuery({
    baseUrl: '',
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('accessToken');
      if (token) headers.set('Authorization', `Bearer ${token}`);
      return headers;
    },
  }),
  endpoints: (builder) => ({
    getTimeTracking: builder.query<TimeTrackingListResponse, { range?: string; date?: string; start_date?: string; end_date?: string; employee_id?: number; page?: number; limit?: number }>({
      query: (params) => addDateParams(ENDPOINTS.TIME_TRACKING.GET_ALL, params),
    }),
    getTimeTrackingDetails: builder.query<TimeTrackingDetails, { employeeId: number; range?: string; date?: string; start_date?: string; end_date?: string }>({
      query: ({ employeeId, ...params }) => addDateParams(ENDPOINTS.TIME_TRACKING.GET_BY_EMPLOYEE(employeeId), params),
    }),
  }),
});

export const { useGetTimeTrackingQuery, useGetTimeTrackingDetailsQuery } = timeTrackingApi;
