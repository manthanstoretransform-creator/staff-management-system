import { configureStore } from '@reduxjs/toolkit';
import { membersApi } from './api/membersApi';
import { projectsApi } from './api/projectsApi';

export const store = configureStore({
  reducer: {
    [membersApi.reducerPath]: membersApi.reducer,
    [projectsApi.reducerPath]: projectsApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      .concat(membersApi.middleware)
      .concat(projectsApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
