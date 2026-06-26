import { useState, useEffect } from 'react';

/**
 * useMediaQuery — reactive matchMedia hook
 * Returns true when the query matches, false otherwise.
 * Re-renders component on change (e.g. resize, orientation change).
 *
 * Usage:
 *   const isMobile = useMediaQuery('(max-width: 768px)');
 */
export default function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.matchMedia(query).matches;
    }
    return false;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia(query);
    const handler = (e) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    setMatches(mql.matches); // re-sync on mount
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return matches;
}
