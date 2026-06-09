import { useQuery } from '@tanstack/react-query';
import { fetchHedge } from '../api/client';
import type { Exposure } from '../components/ExposureToggle';

export function useHedge(pair: string, exposure: Exposure, asOf: string | null) {
  return useQuery({
    queryKey: ['hedge', pair, exposure, asOf],
    queryFn: () => fetchHedge(pair, exposure, asOf ?? undefined),
    retry: false,
    staleTime: 2 * 60 * 1000,
  });
}
