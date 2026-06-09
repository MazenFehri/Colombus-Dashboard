import { useQuery } from '@tanstack/react-query';
import { fetchNews } from '../api/client';

/** Latest news for a pair (keyless RSS, live). Mirrors useCommentary. */
export function useNews(pair: string) {
  return useQuery({
    queryKey: ['news', pair],
    queryFn: () => fetchNews(pair),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
