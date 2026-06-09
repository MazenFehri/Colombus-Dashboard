import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Filler,
  Tooltip,
  type ScriptableContext,
  type ChartOptions,
} from 'chart.js';
import zoomPlugin from 'chartjs-plugin-zoom';
import { Line } from 'react-chartjs-2';
import { useHistory, usePairAnalysis } from '../hooks/usePairAnalysis';
import { DATA_START, RATE_DECIMALS, type Pair } from '../lib/constants';
import { fmtRate, fmtDate } from '../lib/format';
import { parseDay } from '../lib/dates';
import { Card, CardHead } from './ui';

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, zoomPlugin);

// Period presets. `days: null` means "everything back to the data start",
// resolved at render time against the window's end date.
const RANGES: { label: string; days: number | null }[] = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '1Y', days: 365 },
  { label: 'ALL', days: null },
];

const DAY_MS = 86_400_000;

function gradient(ctx: ScriptableContext<'line'>): string | CanvasGradient {
  const { chart } = ctx;
  const { ctx: c, chartArea } = chart;
  if (!chartArea) return 'rgba(200,168,75,0.15)';
  const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  g.addColorStop(0, 'rgba(200,168,75,0.35)');
  g.addColorStop(0.5, 'rgba(43,76,126,0.18)');
  g.addColorStop(1, 'rgba(43,76,126,0)');
  return g;
}

export function RateChart({ pair, asOf }: { pair: Pair; asOf?: string | null }) {
  const [rangeIdx, setRangeIdx] = useState<number>(1); // default 30D
  const [zoomed, setZoomed] = useState(false);
  const chartRef = useRef<ChartJS<'line'>>(null);

  // When time-travelling, anchor the trailing window at the server-resolved
  // trading day (falls back to the picked date until the snapshot loads).
  const { data: snap } = usePairAnalysis(pair, asOf);
  const end = asOf ? snap?.resolvedDate ?? asOf : null;

  // Resolve the preset to a concrete day count. "ALL" spans from the data start
  // to the window's end (today, or the as-of trading day).
  const preset = RANGES[rangeIdx];
  const endDate = end ? parseDay(end) : new Date();
  const allDays = Math.max(1, Math.ceil((endDate.getTime() - parseDay(DATA_START).getTime()) / DAY_MS));
  const days = preset.days ?? allDays;

  const { data: rows = [] } = useHistory(pair, days, end);

  // A new data series invalidates any prior zoom/pan — start fresh.
  useEffect(() => {
    chartRef.current?.resetZoom();
    setZoomed(false);
  }, [pair, days, end]);

  const resetZoom = () => {
    chartRef.current?.resetZoom();
    setZoomed(false);
  };

  // Setting the flag to its current value (true) is a no-op React skips, so only
  // the first zoom/pan re-renders. Combined with the memoized data/options, this
  // stops react-chartjs-2 from running a chart.update() that discards the zoom.
  const markZoomed = useCallback(() => setZoomed(true), []);

  const options = useMemo<ChartOptions<'line'>>(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15, 28, 46, 0.96)',
        borderColor: '#1F3154',
        borderWidth: 1,
        padding: 12,
        titleColor: '#8BA3BF',
        titleFont: { size: 11, weight: 600 },
        bodyColor: '#F0F4F8',
        bodyFont: { family: 'JetBrains Mono', size: 13, weight: 600 },
        displayColors: false,
        callbacks: {
          title: (items) => items[0].label,
          label: (item) => `  ${pair}  ${fmtRate(item.parsed.y ?? 0, RATE_DECIMALS)}`,
        },
      },
      zoom: {
        limits: { x: { minRange: 3 } },
        // Wheel + pinch zoom in/out, drag to pan — all locked to the time axis.
        zoom: {
          wheel: { enabled: true },
          pinch: { enabled: true },
          drag: { enabled: false },
          mode: 'x',
          onZoomComplete: markZoomed,
        },
        pan: {
          enabled: true,
          mode: 'x',
          onPanComplete: markZoomed,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#5E7794', font: { family: 'Inter', size: 11 }, maxRotation: 0, autoSkipPadding: 18 },
      },
      y: {
        grid: { color: 'rgba(31,49,84,0.6)' },
        border: { display: false },
        ticks: {
          color: '#5E7794',
          font: { family: 'JetBrains Mono', size: 11 },
          padding: 8,
          callback: (v) => Number(v).toFixed(RATE_DECIMALS),
        },
      },
    },
  }), [pair, markZoomed]);

  const chartData = useMemo(() => ({
    labels: rows.map((r) => fmtDate(parseDay(r.date))),
    datasets: [
      {
        label: 'Rate',
        data: rows.map((r) => r.rate),
        borderColor: '#C8A84B',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: '#C8A84B',
        pointHoverBorderColor: '#0F1C2E',
        pointHoverBorderWidth: 2,
        tension: 0.32,
        fill: true,
        backgroundColor: gradient,
      },
    ],
  }), [rows]);

  return (
    <Card className="chart-card">
      <CardHead
        title="Historical Rate"
        hint="Scroll to zoom · drag to pan"
        right={
          <div className="chart-controls">
            {zoomed && (
              <button type="button" className="chart-reset" onClick={resetZoom}>
                Reset zoom
              </button>
            )}
            <div className="range-tabs">
              {RANGES.map((r, i) => (
                <button
                  key={r.label}
                  type="button"
                  className={i === rangeIdx ? 'active' : ''}
                  onClick={() => setRangeIdx(i)}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        }
      />
      <div className="chart-wrap">
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </Card>
  );
}
