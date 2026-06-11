import { useState } from 'react';
import { useNews } from '../hooks/useNews';
import { type Pair } from '../lib/constants';
import { Card } from './ui';
import { emailNews } from '../api/client';

export function News({ pair }: { pair: Pair }) {
  const { data, isLoading, isError } = useNews(pair);
  const top = data?.top ?? [];
  const more = data?.more ?? [];

  const [emailing, setEmailing] = useState(false);
  const [emailMsg, setEmailMsg] = useState<string | null>(null);

  const onEmail = async () => {
    setEmailing(true); setEmailMsg(null);
    try { const r = await emailNews(); setEmailMsg(`Sent to ${r.to}`); }
    catch { setEmailMsg('Failed to send'); }
    finally { setEmailing(false); }
  };

  let body: React.ReactNode;

  if (isLoading) {
    body = <p className="news-status">Loading news…</p>;
  } else if (isError) {
    body = <p className="news-status">News is temporarily unavailable.</p>;
  } else if (top.length === 0 && more.length === 0) {
    body = <p className="news-status">No recent news for this pair.</p>;
  } else {
    body = (
      <>
        {top.length > 0 && (
          <div className="news-section">
            <span className="news-section-label">Why it moved</span>
            <ul className="news-list">
              {top.map((item) =>
                item.explanation != null ? (
                  <li key={item.url} className="news-item news-item--explained">
                    <p className="news-explanation">{item.explanation}</p>
                    <div className="ai-sources">
                      <ul>
                        <li>
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            {item.headline}
                          </a>
                          <span className="ai-source-name">{item.source}</span>
                        </li>
                      </ul>
                    </div>
                  </li>
                ) : (
                  <li key={item.url} className="news-item">
                    <div className="ai-sources">
                      <ul>
                        <li>
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            {item.headline}
                          </a>
                          <span className="ai-source-name">{item.source}</span>
                        </li>
                      </ul>
                    </div>
                  </li>
                )
              )}
            </ul>
          </div>
        )}
        {more.length > 0 && (
          <div className="news-section">
            <span className="news-section-label">More news</span>
            <ul className="news-list">
              {more.map((item) => (
                <li key={item.url} className="news-item">
                  <div className="ai-sources">
                    <ul>
                      <li>
                        <a href={item.url} target="_blank" rel="noopener noreferrer">
                          {item.headline}
                        </a>
                        <span className="ai-source-name">{item.source}</span>
                      </li>
                    </ul>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </>
    );
  }

  return (
    <Card className="news-card">
      <div className="news-head">
        <h3>News</h3>
        <button className="news-email-btn" onClick={onEmail} disabled={emailing}>
          {emailing ? 'Sending…' : 'Email me this'}
        </button>
        {emailMsg && <span className="news-email-msg">{emailMsg}</span>}
      </div>
      <div className="news-body">{body}</div>
    </Card>
  );
}
