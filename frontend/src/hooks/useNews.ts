import { useQuery } from '@tanstack/react-query';
import { fetchNews } from '../api/client';
import { isoDay } from '../lib/dates';

/** News for a pair on the latest dashboard date. Mirrors useCommentary. */
export function useNews(pair: string) {
  const day = isoDay(new Date());
  return useQuery({
    queryKey: ['news', pair, day],
    queryFn: () => fetchNews(pair, day),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
