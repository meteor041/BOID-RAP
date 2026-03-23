import { useEffect, useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import { getSearchInsights, type SearchInsightsResponse } from "../../services/meta";

export function SearchInsightsPage() {
  const { token } = useAuth();
  const [insights, setInsights] = useState<SearchInsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    getSearchInsights(token, 12)
      .then((payload) => {
        setInsights(payload);
        setError(null);
      })
      .catch((err: ApiError) => {
        setError(err.message);
      });
  }, [token]);

  return (
    <div className="search-insights-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Search Insights</p>
          <h2 className="page-title">搜索洞察</h2>
          <p className="page-subtitle">用克制的信息面板查看研究搜索习惯、热门主题和最近行为。</p>
        </div>
      </header>

      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      <section className="workspace-grid">
        <div className="main-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">最近搜索</h3>
              <span className="section-note numeric">{insights?.recent_searches.length ?? 0} items</span>
            </div>

            <table className="table">
              <thead>
                <tr>
                  <th>关键词</th>
                  <th>范围</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {insights?.recent_searches.map((item, index) => (
                  <tr key={`${item.keyword}-${index}`}>
                    <td>
                      <div className="table-primary">{item.keyword}</div>
                      <div className="table-secondary numeric">{item.resource_id ?? "-"}</div>
                    </td>
                    <td>{item.scope}</td>
                    <td className="numeric">{item.created_at}</td>
                  </tr>
                )) ?? null}
              </tbody>
            </table>
          </article>

          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">热门关键词</h3>
              <span className="section-note numeric">Total {insights?.total_searches ?? 0}</span>
            </div>

            <div className="insight-grid">
              {insights?.popular_keywords.map((item) => (
                <div className="insight-card" key={item.keyword}>
                  <p className="insight-label">Keyword</p>
                  <p className="insight-value">{item.keyword}</p>
                  <p className="insight-metric numeric">{item.count}</p>
                </div>
              )) ?? null}
            </div>
          </article>
        </div>

        <aside className="side-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">搜索范围统计</h3>
            </div>

            <div className="metric-list">
              {insights?.popular_scopes.map((item) => (
                <div className="metric-row" key={item.scope}>
                  <span>{item.scope}</span>
                  <strong className="numeric">{item.count}</strong>
                </div>
              )) ?? null}
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
