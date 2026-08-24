import { configureStore } from '@reduxjs/toolkit';
import { membersApi } from './api/membersApi';

export const store = configureStore({
  reducer: {
    [membersApi.reducerPath]: membersApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(membersApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
