import { useEffect, useState } from 'react';

/**
 * Returns `value` only once it has stopped changing for `delay` ms.
 *
 * Search boxes are wired straight into RTK Query args, so without this every
 * keystroke was its own request (typing a ten character name fired ten calls,
 * and the responses could land out of order). Debouncing collapses that into
 * one request for the term the user actually finished typing.
 */
export function useDebouncedValue<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    if (value === debounced) return;
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay, debounced]);

  return debounced;
}
