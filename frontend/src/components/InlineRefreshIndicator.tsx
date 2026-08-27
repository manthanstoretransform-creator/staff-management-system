import React from 'react';

/**
 * Shown while cached data on screen is being revalidated in the background.
 *
 * It deliberately does not cover or disable anything: the rows underneath stay
 * readable and clickable, which is the whole point of keeping stale data on
 * screen instead of swapping it for a spinner.
 */
export const InlineRefreshIndicator: React.FC<{ active: boolean; label?: string }> = ({
  active,
  label = 'Updating',
}) => {
  if (!active) return null;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/90 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-500 shadow-sm"
      role="status"
      aria-live="polite"
    >
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      {label}
    </span>
  );
};
