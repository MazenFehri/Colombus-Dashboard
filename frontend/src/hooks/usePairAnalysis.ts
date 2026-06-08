import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchPairAnalysis, fetchHistory } from '../api/client';
import { PAIRS } from '../lib/constants';

/** Aggregated KPI/risk/volatility snapshot for a single pair, as of `asOf`
 *  (null = live/today). The date is part of the query key so it refetches. */
export function usePairAnalysis(pair: string, asOf: string | null = null) {
  return useQuery({
    queryKey: ['analysis', pair, asOf],
    queryFn: () => fetchPairAnalysis(pair, asOf ?? undefined),
  });
}

/** Historical rate series for the chart, trailing window ending at `asOf`
 *  (null = today). */
export function useHistory(pair: string, days: number, asOf: string | null = null) {
  return useQuery({
    queryKey: ['history', pair, days, asOf],
    queryFn: () => fetchHistory(pair, days, asOf ?? undefined),
  });
}

/** Snapshots for every pair — drives the comparison table. */
export function useAllPairs(asOf: string | null = null) {
  return useQueries({
    queries: PAIRS.map((p) => ({
      queryKey: ['analysis', p, asOf],
      queryFn: () => fetchPairAnalysis(p, asOf ?? undefined),
    })),
  });
}
