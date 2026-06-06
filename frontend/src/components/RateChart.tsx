import { useState } from 'react';
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
import { Line } from 'react-chartjs-2';
import { useHistory } from '../hooks/usePairAnalysis';
import { RATE_DECIMALS, type Pair } from '../lib/constants';
import { fmtRate, fmtDate } from '../lib/format';
import { parseDay } from '../lib/dates';
import { Card, CardHead } from './ui';

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip);

const RANGES = [7, 30, 90] as const;

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

export function RateChart({ pair }: { pair: Pair }) {
  const [days, setDays] = useState<number>(30);
  const { data: rows = [] } = useHistory(pair, days);

  const labels = rows.map((r) => fmtDate(parseDay(r.date)));
  const values = rows.map((r) => r.rate);

  const options: ChartOptions<'line'> = {
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
  };

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Rate',
        data: values,
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
  };

  return (
    <Card className="chart-card">
      <CardHead
        title="Historical Rate"
        hint={`${days}-day rate history`}
        right={
          <div className="range-tabs">
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                className={r === days ? 'active' : ''}
                onClick={() => setDays(r)}
              >
                {r}D
              </button>
            ))}
          </div>
        }
      />
      <div className="chart-wrap">
        <Line data={chartData} options={options} />
      </div>
    </Card>
  );
}
