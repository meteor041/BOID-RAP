import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { HighlightedText } from "../../components/common/HighlightedText";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import { cancelJob, getJob, getJobRetrieval, retryJob, type JobItem, type JobRetrievalResponse } from "../../services/jobs";

export function JobPage() {
  const { jobId = "" } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [job, setJob] = useState<JobItem | null>(null);
  const [retrieval, setRetrieval] = useState<JobRetrievalResponse | null>(null);
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !jobId) {
      return;
    }
    const authToken = token;

    let cancelled = false;
    let timeoutId: number | undefined;

    async function load() {
      try {
        const [jobPayload, retrievalPayload] = await Promise.all([
          getJob(authToken, jobId),
          getJobRetrieval(authToken, jobId, keyword || undefined),
        ]);
        if (cancelled) {
          return;
        }
        setJob(jobPayload);
        setRetrieval(retrievalPayload);
        setError(null);

        if (jobPayload.status === "completed" && jobPayload.report_id) {
          timeoutId = window.setTimeout(() => {
            navigate(`/reports/${jobPayload.report_id}`);
          }, 1200);
          return;
        }

        if (jobPayload.status === "queued" || jobPayload.status === "running") {
          timeoutId = window.setTimeout(() => {
            void load();
          }, 2000);
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as ApiError).message);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [jobId, keyword, navigate, token]);

  async function handleCancel() {
    if (!token || !jobId) {
      return;
    }
    const payload = await cancelJob(token, jobId);
    setJob(payload.job);
  }

  async function handleRetry() {
    if (!token || !jobId) {
      return;
    }
    const payload = await retryJob(token, jobId);
    navigate(`/jobs/${payload.job.id}`);
  }

  return (
    <div className="job-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Job</p>
          <h2 className="page-title">任务状态</h2>
          <p className="page-subtitle">跟踪当前研究任务进度，并查看本轮检索结果与来源。</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={handleCancel} type="button">
            取消任务
          </button>
          <button className="btn btn-primary" onClick={handleRetry} type="button">
            重试任务
          </button>
        </div>
      </header>

      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      <section className="workspace-grid">
        <div className="main-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">当前状态</h3>
            </div>
            <div className="report-preview">
              <div className="report-block">
                <p className="report-label">状态</p>
                <p className="report-value numeric">{job?.status ?? "-"}</p>
              </div>
              <div className="report-block">
                <p className="report-label">当前阶段</p>
                <p className="report-value numeric">{job?.current_stage ?? "-"}</p>
              </div>
              <div className="report-block">
                <p className="report-label">进度</p>
                <p className="report-value numeric">{job ? `${job.progress}%` : "-"}</p>
              </div>
              <div className="report-block">
                <p className="report-label">报告 ID</p>
                <p className="report-value numeric">{job?.report_id ?? "-"}</p>
              </div>
            </div>
            {job?.report_id ? (
              <div className="inline-actions">
                <Link className="btn btn-secondary" to={`/reports/${job.report_id}`}>
                  查看报告
                </Link>
              </div>
            ) : null}
          </article>

          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">检索结果</h3>
              <span className="section-note numeric">{retrieval?.provider ?? "-"}</span>
            </div>

            <div className="toolbar-row">
              <input
                className="input toolbar-input"
                onChange={(event) => setKeywordInput(event.target.value)}
                placeholder="按关键词过滤命中文档"
                value={keywordInput}
              />
              <button className="btn btn-primary" onClick={() => setKeyword(keywordInput.trim())} type="button">
                过滤
              </button>
            </div>

            <div className="report-list compact-list">
              {retrieval?.documents.map((document, index) => (
                <article className="card report-card compact-card" key={`${document.url}-${index}`}>
                  <p className="report-card-title compact-title">
                    {document.highlighted_title ? <HighlightedText text={document.highlighted_title} /> : document.title}
                  </p>
                  <p className="report-card-summary compact-summary">
                    {document.highlighted_summary ? (
                      <HighlightedText text={document.highlighted_summary} />
                    ) : (
                      document.summary
                    )}
                  </p>
                  <div className="report-card-meta">
                    <span className="meta-chip numeric">{document.source}</span>
                    {document.category ? <span className="meta-chip">{document.category}</span> : null}
                    {typeof document.score === "number" ? (
                      <span className="meta-chip numeric">{document.score.toFixed(2)}</span>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </article>
        </div>

        <aside className="side-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">检索概况</h3>
            </div>
            <div className="metric-list">
              <div className="metric-row">
                <span>Provider</span>
                <strong className="numeric">{retrieval?.provider ?? "-"}</strong>
              </div>
              <div className="metric-row">
                <span>Cache</span>
                <strong className="numeric">{retrieval?.cache_hit ? "hit" : "miss"}</strong>
              </div>
              <div className="metric-row">
                <span>文档数</span>
                <strong className="numeric">{retrieval?.document_count ?? 0}</strong>
              </div>
              <div className="metric-row">
                <span>命中数</span>
                <strong className="numeric">{retrieval?.matched_document_count ?? retrieval?.document_count ?? 0}</strong>
              </div>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
