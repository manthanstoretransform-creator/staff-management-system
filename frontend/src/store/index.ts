import { configureStore } from '@reduxjs/toolkit';
import { baseApi, rehydrateApiCache } from './api/baseApi';
import { loadPersistedApiCache, startApiCachePersistence } from './persist';

// Importing the domain files registers their endpoints on `baseApi`.
import './api/membersApi';
import './api/projectsApi';
import './api/teamsApi';
import './api/timeTrackingApi';

export const store = configureStore({
  reducer: {
    [baseApi.reducerPath]: baseApi.reducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
});

// Seed the cache from the previous visit before the first render, then keep
// mirroring it. This is what makes a browser refresh paint data immediately
// while the background revalidation runs.
store.dispatch(rehydrateApiCache(loadPersistedApiCache()));
startApiCachePersistence(store);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
