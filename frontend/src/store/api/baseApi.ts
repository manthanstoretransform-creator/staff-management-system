import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { createAction } from '@reduxjs/toolkit';

/**
 * Dispatched once at start-up with the cache we persisted during the previous
 * visit. RTK Query picks it up through `extractRehydrationInfo` below, which is
 * what lets a page paint real rows on the very first frame after a refresh
 * instead of a spinner.
 */
export const rehydrateApiCache = createAction<Record<string, unknown> | undefined>('api/rehydrate');

/**
 * One API slice for the whole client. Every domain file (`membersApi`,
 * `projectsApi`, …) injects its endpoints into this, so there is a single
 * cache, a single middleware and a single place that attaches the auth header.
 * A single cache also means a tag invalidated by one domain is seen by all the
 * others — updating a project can refresh the Teams screens.
 */
export const baseApi = createApi({
  reducerPath: 'api',
  // Keep an unused endpoint's data for 10 minutes so moving between pages and
  // coming back is instant rather than a fresh round trip.
  keepUnusedDataFor: 600,
  // Data already in cache renders immediately; anything older than 60s is
  // revalidated in the background while the stale rows stay on screen.
  refetchOnMountOrArgChange: 60,
  refetchOnReconnect: true,
  baseQuery: fetchBaseQuery({
    // Endpoints supply absolute URLs from src/api/endpoints.ts.
    baseUrl: '',
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('accessToken');
      if (token) headers.set('Authorization', `Bearer ${token}`);
      return headers;
    },
  }),
  extractRehydrationInfo(action, { reducerPath }) {
    if (rehydrateApiCache.match(action)) {
      return action.payload?.[reducerPath] as any;
    }
  },
  tagTypes: ['Member', 'Project', 'Task', 'Team', 'TimeTracking', 'ManualTimeEntry'],
  endpoints: () => ({}),
});
