import { baseApi } from './baseApi';
import { ENDPOINTS } from '../../api/endpoints';

export interface ReportsProjectsQuery {
  from: string;
  to: string;
  member_id?: number[];
  project_id?: number[];
  billing_type?: string;
}

export interface ReportsProjectItem {
  project_id: number;
  project_name: string;
  tracked_seconds: number;
  tracked_hours: number;
  tracked_hours_formatted: string;
  activity_percentage: number;
}

export interface ReportsProjectsResponse {
  start_date: string;
  end_date: string;
  summary: {
    total_project_hours: number;
    total_tracked_seconds: number;
    total_hours_formatted: string;
    average_activity_percentage: number;
    total_members: number;
    total_projects: number;
  };
  projects: ReportsProjectItem[];
}

export const reportsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProjectsReport: builder.query<ReportsProjectsResponse, ReportsProjectsQuery>({
      query: (params) => {
        const queryParams = new URLSearchParams();
        if (params.from) queryParams.append('from', params.from);
        if (params.to) queryParams.append('to', params.to);
        if (params.billing_type) queryParams.append('billing_type', params.billing_type);
        if (params.member_id) {
          params.member_id.forEach(id => queryParams.append('member_id', String(id)));
        }
        if (params.project_id) {
          params.project_id.forEach(id => queryParams.append('project_id', String(id)));
        }
        return {
          url: `${ENDPOINTS.REPORTS.PROJECTS}?${queryParams.toString()}`,
          method: 'GET',
        };
      },
      providesTags: ['Project', 'TimeTracking'],
    }),
  }),
  overrideExisting: false,
});

export const { useGetProjectsReportQuery } = reportsApi;
