import React from 'react';

/**
 * The one way a rejected field explains itself.
 *
 * Renders nothing when there is no message, so a caller can drop it under every
 * input unconditionally. The `id` is the same one
 * `useFormValidation().fieldProps()` puts in the input's `aria-describedby`,
 * which is what connects the message to the field for a screen reader.
 *
 * The rose palette matches `ErrorNote` in `features/member/MemberUi.tsx`, so
 * form errors and page errors read as the same thing.
 */
export const FieldError: React.FC<{ message?: string | null; id?: string }> = ({ message, id }) => {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="mt-1 text-xs font-semibold text-rose-700">
      {message}
    </p>
  );
};

/**
 * A whole-form error banner, for the failure that belongs to the submit rather
 * than to one field (a rejected request, a mismatched confirmation).
 */
export const FormErrorBanner: React.FC<{ message?: string | null }> = ({ message }) => {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-[13px] font-semibold text-rose-700"
    >
      {message}
    </div>
  );
};
