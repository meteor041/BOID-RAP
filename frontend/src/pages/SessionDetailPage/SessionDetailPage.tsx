import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import { addSessionMessage, getSession, runSession, type SessionItem } from "../../services/sessions";

export function SessionDetailPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [session, setSession] = useState<SessionItem | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token || !sessionId) {
      return;
    }
    let active = true;

    getSession(token, sessionId)
      .then((payload) => {
        if (active) {
          setSession(payload);
          setError(null);
        }
      })
      .catch((err: ApiError) => {
        if (active) {
          setError(err.message);
        }
      });

    return () => {
      active = false;
    };
  }, [sessionId, token]);

  async function handleAddMessage() {
    if (!token || !sessionId || !message.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      const payload = await addSessionMessage(token, sessionId, {
        role: "user",
        content: message.trim(),
      });
      setSession(payload);
      setMessage("");
      setError(null);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRun() {
    if (!token || !sessionId) {
      return;
    }
    try {
      const payload = await runSession(token, sessionId, false);
      navigate(`/jobs/${payload.job.id}`);
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  return (
    <div className="session-detail-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Session Detail</p>
          <h2 className="page-title">{session?.object_name ?? "调研会话"}</h2>
          <p className="page-subtitle">
            以时间轴方式查看研究过程、参数和交互记录。整体风格保持金融报告系统的克制秩序感。
          </p>
        </div>
        <div className="page-actions">
          {session?.report_id ? (
            <Link className="btn btn-secondary" to={`/reports/${session.report_id}`}>
              查看报告
            </Link>
          ) : null}
          <button className="btn btn-primary" onClick={() => void handleRun()} type="button">
            发起调研
          </button>
        </div>
      </header>

      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      <section className="workspace-grid">
        <div className="main-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">过程时间轴</h3>
              <span className="section-note numeric">{session?.status ?? "-"}</span>
            </div>

            <div className="timeline">
              {session?.workflow?.length ? (
                session.workflow.map((item, index) => (
                  <div className="timeline-item" key={`${item.stage}-${index}`}>
                    <div className="timeline-marker" />
                    <div className="timeline-content">
                      <div className="timeline-head">
                        <strong className="timeline-stage">{item.stage}</strong>
                        <span className="section-note numeric">{item.created_at ?? "-"}</span>
                      </div>
                      <p className="timeline-detail">{item.detail}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="table-secondary">当前会话还没有流程事件。</p>
              )}
            </div>
          </article>

          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">消息流</h3>
              <span className="section-note numeric">{session?.messages?.length ?? 0} items</span>
            </div>

            <div className="message-list">
              {session?.messages?.length ? (
                session.messages.map((item, index) => (
                  <div className="message-item" key={`${item.role}-${index}`}>
                    <div className="message-head">
                      <span className="message-role">{item.role}</span>
                      <span className="section-note numeric">{item.created_at ?? "-"}</span>
                    </div>
                    <p className="message-content">{item.content}</p>
                  </div>
                ))
              ) : (
                <p className="table-secondary">暂无会话消息。</p>
              )}
            </div>

            <div className="follow-up-panel message-composer">
              <textarea
                className="textarea"
                onChange={(event) => setMessage(event.target.value)}
                placeholder="补充新的研究要求，例如：重点跟踪广告业务和海外监管风险。"
                rows={4}
                value={message}
              />
              <div className="inline-actions">
                <button className="btn btn-secondary" disabled={submitting || !message.trim()} onClick={() => void handleAddMessage()} type="button">
                  {submitting ? "追加中..." : "追加消息"}
                </button>
              </div>
            </div>
          </article>
        </div>

        <aside className="side-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">参数概览</h3>
            </div>

            <div className="metric-list">
              <div className="metric-row">
                <span>对象类型</span>
                <strong>{session?.object_type ?? "-"}</strong>
              </div>
              <div className="metric-row">
                <span>模型 ID</span>
                <strong className="numeric">{session?.model_id ?? "-"}</strong>
              </div>
              <div className="metric-row">
                <span>检索源</span>
                <strong className="numeric">{session?.retrieval_provider ?? "-"}</strong>
              </div>
              <div className="metric-row">
                <span>时间范围</span>
                <strong className="numeric">{session?.time_range ?? "-"}</strong>
              </div>
              <div className="metric-row">
                <span>权威级别</span>
                <strong>{session?.authority_level ?? "-"}</strong>
              </div>
              <div className="metric-row">
                <span>研究深度</span>
                <strong>{session?.depth ?? "-"}</strong>
              </div>
            </div>
          </article>

          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">关注方向</h3>
            </div>

            <div className="keyword-row">
              {session?.focus_areas?.length ? (
                session.focus_areas.map((item) => (
                  <span className="keyword-chip" key={item}>
                    {item}
                  </span>
                ))
              ) : (
                <p className="table-secondary">暂无关注方向。</p>
              )}
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
