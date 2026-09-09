/**
 * Safe normalisation — the small, meaning-preserving changes we *do* make.
 *
 * Mirrors `backend/app/core/validation/sanitizer.py`. The project's position on
 * cleaning input is deliberate:
 *
 * **We reject invalid input. We do not strip the dangerous part and continue.**
 *
 * Silently removing `<script>` from a message and submitting the remainder
 * changes what the user said. So the functions here only do things that cannot
 * change meaning: trimming surrounding whitespace, normalising Unicode to a
 * single canonical spelling, and making line endings consistent.
 *
 * Note in particular what is *not* here: there is no `stripControlCharacters`.
 * Control characters are **rejected on the raw input** by the validators, before
 * any normalisation runs, so that a NUL can never be quietly tidied away.
 */

/**
 * Return `value` in Unicode NFC form.
 *
 * Composed and decomposed spellings of the same accented character look
 * identical on screen but compare unequal. Normalising means "José" typed on a
 * Mac and "José" typed on Windows are the same project name.
 */
export function normalizeUnicode(value: string): string {
  return value.normalize('NFC');
}

/**
 * Collapse CRLF and bare CR line endings to `\n`, so a stored description does
 * not depend on which client submitted it and character counts stay comparable
 * across clients that enforce the same maximum length.
 */
export function normalizeNewlines(value: string): string {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

export type NormalizeTextOptions = {
  /** Keep line breaks. When false (the default) each newline becomes a space. */
  allowNewlines?: boolean;
};

/**
 * The full safe-normalisation pass used before validating text: NFC, then
 * consistent line endings, then (unless newlines are allowed) newline-to-space,
 * then an outer trim.
 *
 * This rejects nothing and removes nothing. A single-line field cannot be
 * smuggled a second line, but no character is ever deleted to make a bad value
 * look good.
 */
export function normalizeText(value: string, options?: NormalizeTextOptions): string {
  const allowNewlines = options != null && options.allowNewlines === true;
  let text = normalizeUnicode(value);
  text = normalizeNewlines(text);
  if (!allowNewlines) {
    text = text.replace(/\n/g, ' ');
  }
  return text.trim();
}

/**
 * Trim an address and lower-case its domain.
 *
 * The local part is left exactly as typed: RFC 5321 says it is case-sensitive,
 * and while nearly every provider treats it case-insensitively that is the
 * provider's choice to make, not ours. The domain genuinely is
 * case-insensitive, so folding it stops `a@Example.com` and `a@example.com`
 * registering as two accounts.
 */
export function normalizeEmail(value: string): string {
  const trimmed = normalizeText(value);
  const at = trimmed.lastIndexOf('@');
  if (at === -1) return trimmed;
  const localPart = trimmed.slice(0, at);
  const domain = trimmed.slice(at + 1);
  return `${localPart}@${domain.toLowerCase()}`;
}

/**
 * Squeeze runs of spaces and tabs into one space, preserving newlines.
 *
 * Used for names, where "Acme   Corp" and "Acme Corp" are the same project and
 * storing both makes duplicate detection useless.
 */
export function collapseWhitespace(value: string): string {
  return normalizeNewlines(value)
    .split('\n')
    .map((line) => line.split(/[^\S\n]+/).filter((part) => part.length > 0).join(' '))
    .join('\n');
}
