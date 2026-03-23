import { useEffect, useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import { listAuditLogs, type AuditLog } from "../../services/admin";

export function AuditLogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    listAuditLogs(token)
      .then((payload) => {
        setLogs(payload.items);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [token]);

  return (
    <div className="admin-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2 className="page-title">审计日志</h2>
          <p className="page-subtitle">当前先提供精简时间线表格，方便核查认证、模型、任务和搜索行为。</p>
        </div>
      </header>

      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      <section className="card section-card">
        <table className="table">
          <thead>
            <tr>
              <th>时间</th>
              <th>动作</th>
              <th>资源类型</th>
              <th>操作者</th>
              <th>资源 ID</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td className="numeric">{log.created_at}</td>
                <td>{log.action}</td>
                <td>{log.resource_type}</td>
                <td className="numeric">{log.actor_user_id ?? "-"}</td>
                <td className="numeric">{log.resource_id ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
