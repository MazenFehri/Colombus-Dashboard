import { useQuery, useQueries } from '@tanstack/react-query';
import { fetchPairAnalysis, fetchHistory } from '../api/client';
import { PAIRS } from '../lib/constants';

/** Aggregated KPI/risk/volatility snapshot for a single pair. */
export function usePairAnalysis(pair: string) {
  return useQuery({
    queryKey: ['analysis', pair],
    queryFn: () => fetchPairAnalysis(pair),
  });
}

/** Historical rate series for the chart. */
export function useHistory(pair: string, days: number) {
  return useQuery({
    queryKey: ['history', pair, days],
    queryFn: () => fetchHistory(pair, days),
  });
}

/** Snapshots for every pair — drives the comparison table. */
export function useAllPairs() {
  return useQueries({
    queries: PAIRS.map((p) => ({
      queryKey: ['analysis', p],
      queryFn: () => fetchPairAnalysis(p),
    })),
  });
}
