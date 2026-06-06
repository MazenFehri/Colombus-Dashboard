import { useQuery } from '@tanstack/react-query';
import { fetchCommentary } from '../api/client';

/** AI market commentary for a pair. Does not retry — a failed generation
 *  falls back to a friendly message in the component. */
export function useCommentary(pair: string) {
  return useQuery({
    queryKey: ['commentary', pair],
    queryFn: () => fetchCommentary(pair),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
