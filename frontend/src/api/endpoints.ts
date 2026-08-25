export const API_BASE_URL = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || "https://staffmanagementsystembackend.vercel.app/api/v1";

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
  }
};
