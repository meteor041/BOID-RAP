import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { HighlightedText } from "../../components/common/HighlightedText";
import { useAuth } from "../../features/auth/AuthContext";
import { listReports, type ReportListItem } from "../../services/reports";
import type { ApiError } from "../../services/http";

export function ReportsPage() {
  const { token } = useAuth();
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    listReports(token, keyword || undefined)
      .then((payload) => {
        if (!active) {
          return;
        }
        setReports(payload.items);
        setSuggestedKeywords(payload.search_meta?.suggested_keywords ?? []);
      })
      .catch((err: ApiError) => {
        if (!active) {
          return;
        }
        setError(err.message);
        setReports([]);
        setSuggestedKeywords([]);
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [keyword, token]);

  return (
    <div className="reports-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Reports</p>
          <h2 className="page-title">报告中心</h2>
          <p className="page-subtitle">按关键词搜索历史报告，并进入结构化详情与追问视图。</p>
        </div>
      </header>

      <section className="card section-card">
        <div className="toolbar-row">
          <input
            className="input toolbar-input"
            onChange={(event) => setKeywordInput(event.target.value)}
            placeholder="输入关键词，如：广告、储能、出海"
            value={keywordInput}
          />
          <button className="btn btn-primary" onClick={() => setKeyword(keywordInput.trim())} type="button">
            搜索
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => {
              setKeywordInput("");
              setKeyword("");
            }}
            type="button"
          >
            清空
          </button>
        </div>

        {suggestedKeywords.length > 0 ? (
          <div className="keyword-row">
            {suggestedKeywords.map((item) => (
              <button
                key={item}
                className="keyword-chip"
                onClick={() => {
                  setKeywordInput(item);
                  setKeyword(item);
                }}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {loading ? <section className="card section-card state-card">正在加载报告...</section> : null}
      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      {!loading && !error ? (
        <section className="report-list">
          {reports.map((report) => (
            <article className="card report-card" key={report.id}>
              <div className="report-card-header">
                <div>
                  <p className="report-card-title">
                    {report.highlighted_title ? (
                      <HighlightedText text={report.highlighted_title} />
                    ) : (
                      report.title
                    )}
                  </p>
                  <p className="table-secondary numeric">{report.created_at}</p>
                </div>
                <Link className="btn btn-secondary" to={`/reports/${report.id}`}>
                  查看详情
                </Link>
              </div>

              <p className="report-card-summary">
                {report.highlighted_summary ? (
                  <HighlightedText text={report.highlighted_summary} />
                ) : (
                  report.summary
                )}
              </p>

              <div className="report-card-meta">
                <span className="meta-chip numeric">Sections {report.matched_section_count ?? 0}</span>
                <span className="meta-chip numeric">Session {report.session_id}</span>
              </div>
            </article>
          ))}

          {reports.length === 0 ? <section className="card section-card state-card">暂无报告数据。</section> : null}
        </section>
      ) : null}
    </div>
  );
}
