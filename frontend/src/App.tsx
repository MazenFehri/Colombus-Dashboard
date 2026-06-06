import { useEffect, useState } from 'react';
import { BrandBar } from './components/layout/BrandBar';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { PairSelector } from './components/PairSelector';
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

        <KpiCards pair={pair} />

        <RiskBadge pair={pair} />

        <section className="focus-grid">
          <RateChart pair={pair} />
          <VolatilityGauge pair={pair} />
        </section>

        <ComparisonTable active={pair} now={now} onSelect={setPair} />

        <MarketIntelligence pair={pair} now={now} />
      </main>

      <Footer />
    </>
  );
}
