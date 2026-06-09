import { useQuery } from '@tanstack/react-query';
import { fetchNews } from '../api/client';
import { isoDay } from '../lib/dates';

/** News for a pair, as of `asOf` (null = live/today). Follows the calendar's
 *  asOf date so it refetches when the user time-travels. Mirrors usePairAnalysis. */
export function useNews(pair: string, asOf: string | null = null) {
  const day = asOf ?? isoDay(new Date());
  return useQuery({
    queryKey: ['news', pair, day],
    queryFn: () => fetchNews(pair, day),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
