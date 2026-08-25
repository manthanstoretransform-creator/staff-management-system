import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { ENDPOINTS } from '../../api/endpoints';

export interface Member {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  date_of_joining: string | null;
  date_of_birth: string | null;
  designation: string;
  created_at?: string;
  updated_at?: string;
}

export interface GetMembersResponse {
  items: Member[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export const membersApi = createApi({
  reducerPath: 'membersApi',
  baseQuery: fetchBaseQuery({ 
    baseUrl: '',
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['Member'],
  endpoints: (builder) => ({
    getMembers: builder.query<GetMembersResponse, { page?: number; limit?: number; role?: string; status?: string }>({
      query: (params) => {
        let queryParams = new URLSearchParams();
        if (params.page) queryParams.append('page', params.page.toString());
        if (params.limit) queryParams.append('limit', params.limit.toString());
        if (params.role && params.role !== 'All') queryParams.append('role', params.role.toLowerCase());
        if (params.status && params.status !== 'All') queryParams.append('status', params.status.toLowerCase());
        
        return {
          url: `${ENDPOINTS.MEMBERS.GET_ALL}?${queryParams.toString()}`,
        }
      },
      providesTags: ['Member'],
    }),
    createMember: builder.mutation<Member, Partial<Member>>({
      query: (body) => ({
        url: ENDPOINTS.MEMBERS.CREATE,
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Member'],
    }),
    updateMember: builder.mutation<Member, { id: number, body: Partial<Member> }>({
      query: ({ id, body }) => ({
        url: ENDPOINTS.MEMBERS.UPDATE(id),
        method: 'PATCH',
        body,
      }),
      invalidatesTags: ['Member'],
    }),
    deleteMember: builder.mutation<void, number>({
      query: (id) => ({
        url: ENDPOINTS.MEMBERS.DELETE(id),
        method: 'DELETE',
      }),
      invalidatesTags: ['Member'],
    }),
  }),
});

export const {
  useGetMembersQuery,
  useCreateMemberMutation,
  useUpdateMemberMutation,
  useDeleteMemberMutation,
} = membersApi;
