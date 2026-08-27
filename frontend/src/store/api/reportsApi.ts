import { baseApi } from './baseApi';
import { ENDPOINTS } from '../../api/endpoints';

export interface ReportQueryParams {
  from: string;
  to: string;
  member_id?: number[];
  project_id?: number[];
  billing_type?: string;
  usage_type?: 'app' | 'url';
}

export interface DetailedLogsQueryParams extends ReportQueryParams {
  dimension?: 'projects' | 'members' | 'tasks' | 'apps';
  search?: string;
  sort_by?: 'date' | 'member' | 'project' | 'task' | 'hours' | 'activity';
  sort_desc?: boolean;
  page?: number;
  limit?: number;
}

export interface ReportGroupedItem {
  id: number | string;
  name: string;
  tracked_seconds: number;
  tracked_hours: number;
  tracked_hours_formatted: string;
  activity_percentage: number;
  meta_label: string;
}

export interface ReportSummary {
  total_hours: number;
  total_tracked_seconds: number;
  total_hours_formatted: string;
  average_activity_percentage: number;
  total_members: number;
  total_entries: number;
  total_projects?: number | null;
  total_tasks?: number | null;
  total_apps?: number | null;
}

export interface ReportGroupedResponse {
  start_date: string;
  end_date: string;
  summary: ReportSummary;
  grouped_data: ReportGroupedItem[];
}

export interface DetailedLogItem {
  id: string;
  date: string;
  member_id: number;
  member_name: string;
  role: string;
  project_id: number | null;
  project_name: string | null;
  task_id: number | null;
  task_name: string | null;
  app: string | null;
  url: string | null;
  tracked_hours: number;
  activity_percentage: number | null;
}

export interface DetailedLogsResponse {
  start_date: string;
  end_date: string;
  items: DetailedLogItem[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

const buildQueryParams = (params: any) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      if (Array.isArray(value)) {
        value.forEach(v => query.append(key, String(v)));
      } else {
        query.append(key, String(value));
      }
    }
  });
  return query.toString();
};

export const reportsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getGroupedReport: builder.query<ReportGroupedResponse, { dimension: string } & ReportQueryParams>({
      query: ({ dimension, ...params }) => ({
        url: `${ENDPOINTS.REPORTS.BASE}/${dimension}?${buildQueryParams(params)}`,
        method: 'GET',
      }),
      providesTags: ['TimeTracking'],
    }),
    getDetailedLogs: builder.query<DetailedLogsResponse, DetailedLogsQueryParams>({
      query: (params) => ({
        url: `${ENDPOINTS.REPORTS.DETAILED_LOGS}?${buildQueryParams(params)}`,
        method: 'GET',
      }),
      providesTags: ['TimeTracking'],
    }),
  }),
  overrideExisting: true,
});

export const { useGetGroupedReportQuery, useGetDetailedLogsQuery } = reportsApi;
