import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { ENDPOINTS } from '../../api/endpoints';

export interface ProjectMetadata {
  roles: any[];
  project_statuses: { id: number; project_status: string; color: string }[];
  task_statuses: { id: number; task_status: string; color: string }[];
}

export interface ProjectUser {
  id: number;
  name: string;
  email: string;
  role: string;
}

export interface ProjectTask {
  id: number;
  project_id: number;
  name: string;
  assignee: ProjectUser | null;
  status: { id: number; name: string; color: string };
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: number;
  project_name: string;
  description: string;
  status: { id: number; name: string; color: string };
  leader: ProjectUser | null;
  employees: ProjectUser[];
  deadline: string | null;
  billing_type: string;
  fixed_hours: string | null;
  organization_id: number;
  created_at: string;
  updated_at: string;
  tasks: ProjectTask[];
  employee_count: number;
  task_count: number;
}

export interface ProjectListResponse {
  items: Project[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

export interface CreateProjectPayload {
  project_name: string;
  description: string;
  status_id: number;
  leader_id: number | null;
  employee_ids: number[];
  deadline: string | null;
  billing_type: string;
  fixed_hours: number | null;
}

export const projectsApi = createApi({
  reducerPath: 'projectsApi',
  baseQuery: fetchBaseQuery({
    baseUrl: '', // Using absolute URLs from ENDPOINTS
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['Project'],
  endpoints: (builder) => ({
    createTask: builder.mutation<ProjectTask, { projectId: number; body: { project_id?: number; name: string; assignee_id: number | null; status_id: number } }>({
      query: ({ projectId, body }) => ({
        url: `http://127.0.0.1:8000/api/v1/projects/${projectId}/tasks`,
        method: 'POST',
        body: { ...body, project_id: projectId },
      }),
      invalidatesTags: [{ type: 'Project', id: 'LIST' }],
    }),
    updateTask: builder.mutation<ProjectTask, { projectId: number; taskId: number; body: { name?: string; assignee_id?: number | null; status_id?: number } }>({
      query: ({ projectId, taskId, body }) => ({
        url: `http://127.0.0.1:8000/api/v1/projects/${projectId}/tasks/${taskId}`,
        method: 'PATCH',
        body,
      }),
      invalidatesTags: [{ type: 'Project', id: 'LIST' }],
    }),
    getProjectMetadata: builder.query<ProjectMetadata, void>({
      query: () => ENDPOINTS.PROJECTS.METADATA,
    }),
    getProjects: builder.query<ProjectListResponse, { page?: number; limit?: number; search?: string; status_id?: number | null; leader_id?: number | null; billing_type?: string | null }>({
      query: (params) => {
        let url = `${ENDPOINTS.PROJECTS.GET_ALL}?page=${params.page || 1}&limit=${params.limit || 20}`;
        if (params.search) url += `&search=${encodeURIComponent(params.search)}`;
        if (params.status_id) url += `&status_id=${params.status_id}`;
        if (params.leader_id) url += `&leader_id=${params.leader_id}`;
        if (params.billing_type) url += `&billing_type=${params.billing_type}`;
        return url;
      },
      providesTags: (result) =>
        result
          ? [
              ...result.items.map(({ id }) => ({ type: 'Project' as const, id })),
              { type: 'Project', id: 'LIST' },
            ]
          : [{ type: 'Project', id: 'LIST' }],
    }),
    getProjectById: builder.query<Project, number>({
      query: (id) => ENDPOINTS.PROJECTS.GET_BY_ID(id),
      providesTags: (result, error, id) => [{ type: 'Project', id }],
    }),
    getAssignableLeaders: builder.query<ProjectUser[], void>({
      query: () => ENDPOINTS.PROJECTS.ASSIGNABLE_LEADERS,
    }),
    getAssignableEmployees: builder.query<ProjectUser[], void>({
      query: () => ENDPOINTS.PROJECTS.ASSIGNABLE_EMPLOYEES,
    }),
    createProject: builder.mutation<Project, CreateProjectPayload>({
      query: (body) => ({
        url: ENDPOINTS.PROJECTS.CREATE,
        method: 'POST',
        body,
      }),
      invalidatesTags: [{ type: 'Project', id: 'LIST' }],
    }),
    updateProject: builder.mutation<Project, { id: number; body: Partial<CreateProjectPayload> }>({
      query: ({ id, body }) => ({
        url: ENDPOINTS.PROJECTS.UPDATE(id),
        method: 'PATCH',
        body,
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Project', id }, { type: 'Project', id: 'LIST' }],
    }),
    deleteProject: builder.mutation<void, number>({
      query: (id) => ({
        url: ENDPOINTS.PROJECTS.DELETE(id),
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Project', id: 'LIST' }],
    }),
  }),
});

export const {
  useGetProjectMetadataQuery,
  useGetProjectsQuery,
  useGetProjectByIdQuery,
  useGetAssignableLeadersQuery,
  useGetAssignableEmployeesQuery,
  useCreateProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
  useCreateTaskMutation,
  useUpdateTaskMutation,
} = projectsApi;
