export const API_BASE_URL = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || '/api';

export const ENDPOINTS = {
  MEMBERS: {
    GET_ALL: `${API_BASE_URL}/members`,
    GET_BY_ID: (id: string | number) => `${API_BASE_URL}/members/${id}`,
    CREATE: `${API_BASE_URL}/members`,
    UPDATE: (id: string | number) => `${API_BASE_URL}/members/${id}`,
    DELETE: (id: string | number) => `${API_BASE_URL}/members/${id}`,
  },
  PROJECTS: {
    METADATA: `http://127.0.0.1:8000/api/v1/project-management/metadata`,
    GET_ALL: `http://127.0.0.1:8000/api/v1/projects`,
    GET_BY_ID: (id: string | number) => `http://127.0.0.1:8000/api/v1/projects/${id}`,
    CREATE: `http://127.0.0.1:8000/api/v1/projects`,
    UPDATE: (id: string | number) => `http://127.0.0.1:8000/api/v1/projects/${id}`,
    DELETE: (id: string | number) => `http://127.0.0.1:8000/api/v1/projects/${id}`,
    ASSIGNABLE_LEADERS: `http://127.0.0.1:8000/api/v1/projects/assignable-leaders`,
    ASSIGNABLE_EMPLOYEES: `http://127.0.0.1:8000/api/v1/projects/assignable-employees`,
  }
};
