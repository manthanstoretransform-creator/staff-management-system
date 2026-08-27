import { API_BASE_URL } from './utils';

export { API_BASE_URL };

export const ENDPOINTS = {
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
};
