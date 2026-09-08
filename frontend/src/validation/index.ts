/**
 * The web client's input-validation framework.
 *
 * A mirror of `backend/app/core/validation`, so the browser can reject what the
 * API would reject, using the same limits, the same patterns and the same
 * wording — and so nothing in `src/features` has to invent a length cap or an
 * email regex of its own ever again.
 *
 * Import from here, not from the individual modules:
 *
 * ```ts
 * import { useFormValidation, FieldError, validateEmail, NAME_MAX_LENGTH } from '../../validation';
 * ```
 *
 * The three catalogues — backend, desktop, frontend — are kept in step by hand.
 * Change a limit in one and you must change it in all three.
 */

export * from './rules';
export * from './sanitizer';
export * from './validators';
export * from './useFormValidation';
export { FieldError, FormErrorBanner } from './FieldError';
