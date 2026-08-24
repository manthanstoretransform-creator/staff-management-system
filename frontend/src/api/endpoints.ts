export const API_BASE_URL = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || '/api';

export const ENDPOINTS = {
  MEMBERS: {
    GET_ALL: `${API_BASE_URL}/members`,
    GET_BY_ID: (id: string | number) => `${API_BASE_URL}/members/${id}`,
    CREATE: `${API_BASE_URL}/members`,
    UPDATE: (id: string | number) => `${API_BASE_URL}/members/${id}`,
    DELETE: (id: string | number) => `${API_BASE_URL}/members/${id}`,
  }
};
