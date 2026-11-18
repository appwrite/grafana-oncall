import { useMemo, useSyncExternalStore } from 'react';

export function useMediaQuery({ query }: { query: string }) {
  const media = useMemo(() => window.matchMedia(query), [query]);
  return useSyncExternalStore(
    (notify) => {
      media.addEventListener('change', notify);
      return () => media.removeEventListener('change', notify);
    },
    () => media.matches,
    () => false
  );
}
