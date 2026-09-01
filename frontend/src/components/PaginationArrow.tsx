import React from 'react';

/**
 * The previous/next control used by every paginated list.
 *
 * It lives here rather than in each screen's own `Pagination` because the
 * arrows were drifting apart — some pages drew bare `←`/`→` text glyphs, others
 * a chevron — and a control that means the same thing everywhere should look
 * the same everywhere.
 *
 * Disabled is styled rather than merely dimmed: at the first or last page the
 * button loses its shadow and stops responding to the pointer, so "there is
 * nothing further this way" reads before the click, not after it.
 */
export const PaginationArrow: React.FC<{
  direction: 'prev' | 'next';
  disabled?: boolean;
  onClick: () => void;
}> = ({ direction, disabled = false, onClick }) => (
  <button
    type="button"
    disabled={disabled}
    onClick={onClick}
    aria-label={direction === 'prev' ? 'Previous page' : 'Next page'}
    className={
      'flex h-8 w-8 items-center justify-center rounded-lg border bg-white text-slate-500 shadow-sm transition ' +
      'hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 active:scale-95 ' +
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 ' +
      'disabled:pointer-events-none disabled:border-slate-100 disabled:bg-slate-50 disabled:text-slate-300 disabled:shadow-none ' +
      'border-slate-200'
    }
  >
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2.5}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d={direction === 'prev' ? 'M15 19l-7-7 7-7' : 'M9 5l7 7-7 7'}
      />
    </svg>
  </button>
);
