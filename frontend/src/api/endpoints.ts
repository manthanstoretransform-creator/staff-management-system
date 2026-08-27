import { API_BASE_URL } from './utils';

export { API_BASE_URL };

/**
 * Every backend URL the web client talks to lives here.
 * Nothing else in the app builds an API URL by hand — if you need a new call,
 * add it to this map first and reference it from the RTK Query slice.
 */
export const ENDPOINTS = {
  AUTH: {
    LOGIN: `${API_BASE_URL}/auth/login`,
    ME: `${API_BASE_URL}/auth/me`,
  },
  MEMBERS: {
    GET_ALL: `${API_BASE_URL}/members`,
    GET_BY_ID: (id: string | number) => `${API_BASE_URL}/members/${id}`,
    CREATE: `${API_BASE_URL}/members`,
    UPDATE: (id: string | number) => `${API_BASE_URL}/members/${id}`,
    DELETE: (id: string | number) => `${API_BASE_URL}/members/${id}`,
  },
  PROJECTS: {
    BASE: `${API_BASE_URL}/projects`,
    METADATA: `${API_BASE_URL}/project-management/metadata`,
    GET_ALL: `${API_BASE_URL}/projects`,
    GET_BY_ID: (id: string | number) => `${API_BASE_URL}/projects/${id}`,
    CREATE: `${API_BASE_URL}/projects`,
    UPDATE: (id: string | number) => `${API_BASE_URL}/projects/${id}`,
    DELETE: (id: string | number) => `${API_BASE_URL}/projects/${id}`,
    ASSIGNABLE_LEADERS: `${API_BASE_URL}/projects/assignable-leaders`,
    ASSIGNABLE_EMPLOYEES: `${API_BASE_URL}/projects/assignable-employees`,
    TASKS: (projectId: string | number) => `${API_BASE_URL}/projects/${projectId}/tasks`,
    TASK_BY_ID: (projectId: string | number, taskId: string | number) =>
      `${API_BASE_URL}/projects/${projectId}/tasks/${taskId}`,
  },
  TEAMS: {
    SUMMARY: `${API_BASE_URL}/teams/summary`,
    LEADERS: `${API_BASE_URL}/teams/leaders`,
    LEADER_BY_ID: (id: string | number) => `${API_BASE_URL}/teams/leaders/${id}`,
    LEADER_PROJECTS: (id: string | number) => `${API_BASE_URL}/teams/leaders/${id}/projects`,
    PROJECT_BY_ID: (id: string | number) => `${API_BASE_URL}/teams/projects/${id}`,
    PROJECT_MEMBER: (projectId: string | number, memberId: string | number) => `${API_BASE_URL}/teams/projects/${projectId}/members/${memberId}`,
  },
  TIME_TRACKING: {
    GET_ALL: `${API_BASE_URL}/time-tracking`,
    GET_BY_EMPLOYEE: (id: string | number) => `${API_BASE_URL}/time-tracking/${id}`,
  },
  MANUAL_TIME_ENTRIES: {
    BASE: `${API_BASE_URL}/manual-time-entries`,
  },
  REPORTS: {
    BASE: `${API_BASE_URL}/reports`,
    DETAILED_LOGS: `${API_BASE_URL}/reports/detailed-logs`,
  },
};
