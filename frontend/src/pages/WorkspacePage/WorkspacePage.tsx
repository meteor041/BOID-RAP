import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import { getObjectTypes, getRetrievalProviders } from "../../services/meta";
import { listModels, type ModelItem } from "../../services/models";
import { createSession, getSession, listSessions, runSession, type SessionItem } from "../../services/sessions";

export function WorkspacePage() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [selectedSession, setSelectedSession] = useState<SessionItem | null>(null);
  const [objectTypes, setObjectTypes] = useState<Array<"company" | "stock" | "commodity">>([]);
  const [retrievalProviders, setRetrievalProviders] = useState<Array<{ name: string; enabled: boolean }>>([]);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    object_name: "腾讯控股",
    object_type: "company" as "company" | "stock" | "commodity",
    model_id: "",
    retrieval_provider: "tavily_search",
    focus_areas: "游戏,广告,出海",
  });

  useEffect(() => {
    if (!token) {
      return;
    }
    let active = true;

    Promise.all([getObjectTypes(), getRetrievalProviders(), listSessions(token), listModels(token, form.object_type)])
      .then(([typesPayload, providersPayload, sessionsPayload, modelsPayload]) => {
        if (!active) {
          return;
        }
        setObjectTypes(typesPayload.items);
        setRetrievalProviders(providersPayload.items);
        setSessions(sessionsPayload.items);
        setModels(modelsPayload.items);
        setSelectedSession(sessionsPayload.items[0] ?? null);
        setForm((current) => ({
          ...current,
          model_id: current.model_id || modelsPayload.items[0]?.id || "",
        }));
      })
      .catch((err: ApiError) => {
        if (active) {
          setError(err.message);
        }
      });

    return () => {
      active = false;
    };
  }, [form.object_type, token]);

  useEffect(() => {
    if (!token || !selectedSession?.id) {
      return;
    }
    let active = true;
    getSession(token, selectedSession.id)
      .then((payload) => {
        if (active) {
          setSelectedSession(payload);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [selectedSession?.id, token]);

  async function handleCreateSession() {
    if (!token || !form.model_id) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = await createSession(token, {
        object_name: form.object_name,
        object_type: form.object_type,
        model_id: form.model_id,
        retrieval_provider: form.retrieval_provider,
        focus_areas: form.focus_areas
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      const sessionsPayload = await listSessions(token);
      setSessions(sessionsPayload.items);
      setSelectedSession(payload);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRunSession() {
    if (!token || !selectedSession?.id) {
      return;
    }
    try {
      const payload = await runSession(token, selectedSession.id, false);
      navigate(`/jobs/${payload.job.id}`);
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  return (
    <div className="workspace-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h2 className="page-title">调研工作台</h2>
          <p className="page-subtitle">
            当前版本先提供金融终端风格的前端骨架，用于后续接入真实列表、会话与任务数据。
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" type="button">
            新建会话
          </button>
          <button className="btn btn-primary" type="button">
            发起调研
          </button>
        </div>
      </header>

      <section className="workspace-grid">
        <div className="main-column workspace-main-column">
          <article className="card section-card session-list-card">
            <div className="section-head">
              <h3 className="section-title">会话列表</h3>
              <span className="section-note numeric">{sessions.length} records</span>
            </div>

            <div className="session-table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>对象</th>
                    <th>类型</th>
                    <th>状态</th>
                    <th>更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr
                      className={selectedSession?.id === session.id ? "table-row-active" : ""}
                      key={session.id}
                      onClick={() => setSelectedSession(session)}
                    >
                      <td>
                        <div className="table-primary">{session.object_name}</div>
                        <div className="table-secondary numeric">{session.id}</div>
                      </td>
                      <td>{session.object_type}</td>
                      <td>
                        <span className={`status-pill status-${session.status}`}>{session.status}</span>
                      </td>
                      <td className="numeric">{session.updated_at ?? session.created_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="card section-card session-summary-card">
            <div className="section-head">
              <h3 className="section-title">当前研究摘要</h3>
              <span className="section-note">结构化视图预览</span>
            </div>

            <div className="report-preview">
              <div className="report-block">
                <p className="report-label">对象名称</p>
                <p className="report-value">{selectedSession?.object_name ?? "-"}</p>
              </div>
              <div className="report-block">
                <p className="report-label">研究方向</p>
                <p className="report-value">{selectedSession?.focus_areas?.join("、") || "未设置"}</p>
              </div>
              <div className="report-block">
                <p className="report-label">运行阶段</p>
                <p className="report-value numeric">
                  {selectedSession?.workflow?.[selectedSession.workflow.length - 1]?.stage ?? selectedSession?.status ?? "-"}
                </p>
              </div>
              <div className="report-block report-wide">
                <p className="report-label">系统说明</p>
                <p className="report-value">
                  {selectedSession?.workflow?.[selectedSession.workflow.length - 1]?.detail ??
                    "创建会话后可直接启动研究任务。"}
                </p>
              </div>
            </div>

            {selectedSession?.report_id ? (
              <div className="inline-actions">
                <Link className="btn btn-secondary" to={`/workspace/sessions/${selectedSession.id}`}>
                  查看时间轴
                </Link>
                <Link className="btn btn-secondary" to={`/reports/${selectedSession.report_id}`}>
                  查看最新报告
                </Link>
              </div>
            ) : selectedSession ? (
              <div className="inline-actions">
                <Link className="btn btn-secondary" to={`/workspace/sessions/${selectedSession.id}`}>
                  查看时间轴
                </Link>
              </div>
            ) : null}
          </article>
        </div>

        <aside className="side-column">
          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">调研参数</h3>
            </div>

            <div className="form-stack">
              <label className="form-field">
                <span className="form-label">对象名称</span>
                <input
                  className="input"
                  onChange={(event) => setForm((current) => ({ ...current, object_name: event.target.value }))}
                  value={form.object_name}
                />
              </label>

              <label className="form-field">
                <span className="form-label">对象类型</span>
                <select
                  className="input"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      object_type: event.target.value as "company" | "stock" | "commodity",
                      model_id: "",
                    }))
                  }
                  value={form.object_type}
                >
                  {objectTypes.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>

              <label className="form-field">
                <span className="form-label">模型</span>
                <select
                  className="input"
                  onChange={(event) => setForm((current) => ({ ...current, model_id: event.target.value }))}
                  value={form.model_id}
                >
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="form-field">
                <span className="form-label">检索源</span>
                <select
                  className="input numeric"
                  onChange={(event) => setForm((current) => ({ ...current, retrieval_provider: event.target.value }))}
                  value={form.retrieval_provider}
                >
                  {retrievalProviders
                    .filter((provider) => provider.enabled)
                    .map((provider) => (
                      <option key={provider.name} value={provider.name}>
                        {provider.name}
                      </option>
                    ))}
                </select>
              </label>

              <label className="form-field">
                <span className="form-label">关注方向</span>
                <input
                  className="input"
                  onChange={(event) => setForm((current) => ({ ...current, focus_areas: event.target.value }))}
                  value={form.focus_areas}
                />
              </label>

              {error ? <p className="form-error">{error}</p> : null}

              <div className="login-actions">
                <button className="btn btn-secondary" disabled={submitting} onClick={handleCreateSession} type="button">
                  {submitting ? "创建中..." : "新建会话"}
                </button>
                <button className="btn btn-primary" disabled={!selectedSession} onClick={handleRunSession} type="button">
                  发起调研
                </button>
              </div>
            </div>
          </article>

          <article className="card section-card">
            <div className="section-head">
              <h3 className="section-title">来源观察</h3>
            </div>

            <ul className="source-list">
              {(retrievalProviders.filter((provider) => provider.enabled).map((provider) => provider.name) || []).map((citation) => (
                <li key={citation} className="source-item numeric">
                  {citation}
                </li>
              ))}
            </ul>
          </article>
        </aside>
      </section>
    </div>
  );
}
