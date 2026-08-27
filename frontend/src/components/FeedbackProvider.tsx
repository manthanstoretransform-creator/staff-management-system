import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

type ToastKind = 'success' | 'error' | 'info';
type Toast = { id: number; kind: ToastKind; message: string };
type ConfirmRequest = { title: string; message: string; resolve: (confirmed: boolean) => void };

type FeedbackContextValue = {
  showToast: (message: string, kind?: ToastKind) => void;
  confirmAction: (title: string, message: string) => Promise<boolean>;
};

const FeedbackContext = createContext<FeedbackContextValue | undefined>(undefined);

const kindStyles: Record<ToastKind, { accent: string; icon: string }> = {
  success: { accent: '#10B981', icon: '✓' },
  error: { accent: '#F43F5E', icon: '!' },
  info: { accent: '#3B82F6', icon: 'i' },
};

export const FeedbackProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmRequest, setConfirmRequest] = useState<ConfirmRequest | null>(null);

  const showToast = (message: string, kind: ToastKind = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4200);
  };

  const confirmAction = (title: string, message: string) => new Promise<boolean>((resolve) => {
    setConfirmRequest({ title, message, resolve });
  });

  const closeConfirm = (confirmed: boolean) => {
    confirmRequest?.resolve(confirmed);
    setConfirmRequest(null);
  };

  return (
    <FeedbackContext.Provider value={{ showToast, confirmAction }}>
      {children}
      <div className="pointer-events-none fixed right-5 top-5 z-[100] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-3">
        {toasts.map((toast) => {
          const style = kindStyles[toast.kind];
          return (
            <div key={toast.id} className="pointer-events-auto flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-2xl" style={{ borderLeft: `4px solid ${style.accent}` }} role="status">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-sm font-black text-white" style={{ backgroundColor: style.accent }}>{style.icon}</span>
              <p className="flex-1 pt-0.5 text-sm font-semibold leading-5 text-slate-700">{toast.message}</p>
              <button type="button" onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))} className="text-lg leading-none text-slate-300 transition hover:text-slate-600" aria-label="Dismiss notification">×</button>
            </div>
          );
        })}
      </div>
      {confirmRequest && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-xl font-black text-amber-500">!</div>
            <h2 className="mt-4 text-xl font-black text-slate-800">{confirmRequest.title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">{confirmRequest.message}</p>
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => closeConfirm(false)} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50">Cancel</button>
              <button type="button" onClick={() => closeConfirm(true)} className="rounded-lg bg-rose-500 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-rose-600">Confirm</button>
            </div>
          </div>
        </div>
      )}
    </FeedbackContext.Provider>
  );
};

export const useFeedback = () => {
  const context = useContext(FeedbackContext);
  if (!context) throw new Error('useFeedback must be used within a FeedbackProvider');
  return context;
};
