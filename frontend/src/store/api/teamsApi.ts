import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { ENDPOINTS } from '../../api/endpoints';

export interface TeamSummary {
  team_leaders: number;
  employees: number;
  total_projects: number;
  active_projects: number;
}

export interface TeamCompletion {
  completed: number;
  total: number;
  percentage: number;
}

export interface TeamMemberPreview {
  id: number;
  name: string;
  designation: string;
  initials: string;
}

export interface TeamLeader {
  id: number;
  name: string;
  email: string;
  designation: string;
  role: string;
  total_projects: number;
  total_members: number;
  active_projects: number;
  completed_projects: number;
  completion: TeamCompletion;
  members_preview: TeamMemberPreview[];
}

export interface TeamLeaderListResponse {
  items: TeamLeader[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

export interface TeamLeaderResponse {
  leader: TeamLeader;
}

export interface LeaderProjectsResponse {
  items: any[];
  status_counts: Record<string, number>;
  filters: any[];
  pagination: any;
}

export interface TeamProject {
  id: number;
  project_name: string;
  description: string;
  status: {
    id: number;
    name: string;
    color: string;
  };
  created_at: string;
  deadline: string;
  leader: {
    id: number;
    name: string;
    designation: string;
    initials: string;
  };
  members: Record<string, any>;
  task_progress: TeamCompletion;
  unassigned_task_count: number;
}

export interface TeamProjectMember {
  id: number;
  name: string;
  designation: string;
  initials: string;
  role: string;
  total_tasks: number;
  completed_tasks: number;
  task_progress: TeamCompletion;
  tasks: Array<{
    id: number;
    name: string;
    status: {
      id: number;
      name: string;
      color: string;
    };
  }>;
  project_id: number;
}

export const teamsApi = createApi({
  reducerPath: 'teamsApi',
  baseQuery: fetchBaseQuery({
    baseUrl: '',
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  endpoints: (builder) => ({
    getTeamSummary: builder.query<TeamSummary, void>({
      query: () => ENDPOINTS.TEAMS.SUMMARY,
    }),
    getTeamLeaders: builder.query<TeamLeaderListResponse, { page?: number; limit?: number; search?: string }>({
      query: (params) => {
        let url = `${ENDPOINTS.TEAMS.LEADERS}?page=${params.page || 1}&limit=${params.limit || 20}`;
        if (params.search) url += `&search=${encodeURIComponent(params.search)}`;
        return url;
      },
    }),
    getTeamLeaderById: builder.query<TeamLeaderResponse, number>({
      query: (id) => ENDPOINTS.TEAMS.LEADER_BY_ID(id),
    }),
    getLeaderProjects: builder.query<LeaderProjectsResponse, { leaderId: number; page?: number; limit?: number; search?: string; status_id?: number | null }>({
      query: (params) => {
        let url = `${ENDPOINTS.TEAMS.LEADER_PROJECTS(params.leaderId)}?page=${params.page || 1}&limit=${params.limit || 20}`;
        if (params.search) url += `&search=${encodeURIComponent(params.search)}`;
        if (params.status_id) url += `&status_id=${params.status_id}`;
        return url;
      },
    }),
    getTeamProjectById: builder.query<TeamProject, number>({
      query: (id) => ENDPOINTS.TEAMS.PROJECT_BY_ID(id),
    }),
    getTeamProjectMember: builder.query<TeamProjectMember, { projectId: number; memberId: number }>({
      query: ({ projectId, memberId }) => ENDPOINTS.TEAMS.PROJECT_MEMBER(projectId, memberId),
    }),
  }),
});

export const {
  useGetTeamSummaryQuery,
  useGetTeamLeadersQuery,
  useGetTeamLeaderByIdQuery,
  useGetLeaderProjectsQuery,
  useGetTeamProjectByIdQuery,
  useGetTeamProjectMemberQuery,
} = teamsApi;
