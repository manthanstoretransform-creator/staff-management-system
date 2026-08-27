import { configureStore } from '@reduxjs/toolkit';
import { membersApi } from './api/membersApi';
import { projectsApi } from './api/projectsApi';
import { teamsApi } from './api/teamsApi';
import { timeTrackingApi } from './api/timeTrackingApi';

export const store = configureStore({
  reducer: {
    [membersApi.reducerPath]: membersApi.reducer,
    [projectsApi.reducerPath]: projectsApi.reducer,
    [teamsApi.reducerPath]: teamsApi.reducer,
    [timeTrackingApi.reducerPath]: timeTrackingApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      .concat(membersApi.middleware)
      .concat(projectsApi.middleware)
      .concat(teamsApi.middleware)
      .concat(timeTrackingApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
