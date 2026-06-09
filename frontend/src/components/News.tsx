import { useNews } from '../hooks/useNews';
import { type Pair } from '../lib/constants';
import type { NewsArticle } from '../api/client';
import { Card, CardHead } from './ui';

function HeadlineItem({ a }: { a: NewsArticle }) {
  return (
    <li className="news-item">
      <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a>
      <span className="news-meta mono">{a.source}</span>
    </li>
  );
}

function ExplainedItem({ a }: { a: NewsArticle }) {
  if (!a.explanation) return <HeadlineItem a={a} />;
  return (
    <li className="news-explained">
      <p className="news-paragraph">{a.explanation}</p>
      <a className="news-source" href={a.url} target="_blank" rel="noopener noreferrer">
        {a.title} · <span className="mono">{a.source}</span>
      </a>
    </li>
  );
}

export function News({ pair }: { pair: Pair }) {
  const { data, isLoading, isError } = useNews(pair);
  const top = data?.top ?? [];
  const more = data?.more ?? [];
  const empty = !isLoading && !isError && top.length === 0 && more.length === 0;

  return (
    <Card className="news-card">
      <CardHead title="News" hint={`What's moving ${pair}`} />
      {isLoading && <p className="news-status">Loading news…</p>}
      {isError && <p className="news-status">News is temporarily unavailable.</p>}
      {empty && <p className="news-status">No news found for this date.</p>}
      {top.length > 0 && (
        <>
          <h4 className="news-subhead">Why it moved</h4>
          <ul className="news-list">{top.map((a) => <ExplainedItem key={a.url} a={a} />)}</ul>
        </>
      )}
      {more.length > 0 && (
        <>
          <h4 className="news-subhead">More news</h4>
          <ul className="news-list">{more.map((a) => <HeadlineItem key={a.url} a={a} />)}</ul>
        </>
      )}
    </Card>
  );
}
