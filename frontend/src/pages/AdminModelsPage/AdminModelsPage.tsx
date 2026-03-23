import { useEffect, useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import { listAdminModels, updateAdminModel, type AdminModel } from "../../services/admin";

export function AdminModelsPage() {
  const { token } = useAuth();
  const [models, setModels] = useState<AdminModel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    listAdminModels(token)
      .then((payload) => {
        setModels(payload.items);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [token]);

  async function handleToggle(model: AdminModel) {
    if (!token) {
      return;
    }
    setBusyId(model.id);
    try {
      const payload = await updateAdminModel(token, model.id, { enabled: !model.enabled });
      setModels((current) => current.map((item) => (item.id === model.id ? payload : item)));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="admin-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2 className="page-title">模型管理</h2>
          <p className="page-subtitle">查看模型提供方、适用对象和权限范围，并支持启停。</p>
        </div>
      </header>

      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      <section className="card section-card">
        <table className="table">
          <thead>
            <tr>
              <th>模型</th>
              <th>Provider</th>
              <th>适用对象</th>
              <th>权限</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.id}>
                <td>
                  <div className="table-primary">{model.name}</div>
                  <div className="table-secondary numeric">{model.id}</div>
                </td>
                <td>{model.provider}</td>
                <td>{model.recommended_for.join(" / ")}</td>
                <td>{model.permissions.join(" / ")}</td>
                <td>
                  <span className={`status-pill ${model.enabled ? "status-completed" : "status-draft"}`}>
                    {model.enabled ? "enabled" : "disabled"}
                  </span>
                </td>
                <td>
                  <button className="btn btn-secondary btn-small" disabled={busyId === model.id} onClick={() => void handleToggle(model)} type="button">
                    {model.enabled ? "停用" : "启用"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
