import { useEffect, useState } from 'react';
import { BrandBar } from './components/layout/BrandBar';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { PairSelector } from './components/PairSelector';
import { DatePicker } from './components/DatePicker';
import { AsOfBadge } from './components/AsOfBadge';
import { KpiCards } from './components/KpiCards';
import { RiskBadge } from './components/RiskBadge';
import { RateChart } from './components/RateChart';
import { VolatilityGauge } from './components/VolatilityGauge';
import { ComparisonTable } from './components/ComparisonTable';
import { MarketIntelligence } from './components/MarketIntelligence';
import { PAIRS, type Pair } from './lib/constants';

export default function App() {
  const [pair, setPair] = useState<Pair>(PAIRS[0]);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [now, setNow] = useState<Date>(new Date());
  // null = live/today; a YYYY-MM-DD string time-travels the dashboard (not the AI card).
  const [asOf, setAsOf] = useState<string | null>(null);

  // Live "last updated" clock.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Theme toggle drives the `light` class on <body>, matching the design tokens.
  useEffect(() => {
    document.body.classList.toggle('light', theme === 'light');
  }, [theme]);

  return (
    <>
      <BrandBar />
      <Header
        now={now}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
      />

      <main>
        <PairSelector active={pair} onSelect={setPair} />

        <div className="time-travel-bar">
          <DatePicker asOf={asOf} onChange={setAsOf} />
          {asOf && <AsOfBadge pair={pair} asOf={asOf} />}
        </div>

        <KpiCards pair={pair} asOf={asOf} />

        <RiskBadge pair={pair} asOf={asOf} />

        <section className="focus-grid">
          <RateChart pair={pair} asOf={asOf} />
          <VolatilityGauge pair={pair} asOf={asOf} />
        </section>

        <ComparisonTable active={pair} now={now} onSelect={setPair} asOf={asOf} />

        <MarketIntelligence pair={pair} now={now} />
      </main>

      <Footer />
    </>
  );
}
