import { useEffect, useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";
import type { ApiError } from "../../services/http";
import {
  listAdminUsers,
  resetAdminUserPassword,
  softDeleteAdminUser,
  updateAdminUserStatus,
  type AdminUser,
} from "../../services/admin";

export function AdminUsersPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    listAdminUsers(token)
      .then((payload) => {
        setUsers(payload.items);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [token]);

  async function handleToggle(user: AdminUser) {
    if (!token) {
      return;
    }
    setBusyUserId(user.id);
    try {
      const payload = await updateAdminUserStatus(token, user.id, !user.enabled);
      setUsers((current) => current.map((item) => (item.id === user.id ? payload : item)));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleReset(user: AdminUser) {
    if (!token) {
      return;
    }
    const newPassword = window.prompt(`为 ${user.username} 输入新密码`, "reset123456");
    if (!newPassword) {
      return;
    }
    setBusyUserId(user.id);
    try {
      await resetAdminUserPassword(token, user.id, newPassword);
      setError(null);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleDelete(user: AdminUser) {
    if (!token) {
      return;
    }
    if (!window.confirm(`确认软删除用户 ${user.username} 吗？`)) {
      return;
    }
    setBusyUserId(user.id);
    try {
      await softDeleteAdminUser(token, user.id);
      setUsers((current) => current.filter((item) => item.id !== user.id));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <div className="admin-page fade-in">
      <header className="page-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2 className="page-title">用户管理</h2>
          <p className="page-subtitle">管理账号状态、密码重置与软删除。界面保持表格化和低装饰。</p>
        </div>
      </header>

      {error ? <section className="card section-card state-card state-error">{error}</section> : null}

      <section className="card section-card">
        <table className="table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>状态</th>
              <th>删除时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>
                  <div className="table-primary">{user.username}</div>
                  <div className="table-secondary numeric">{user.id}</div>
                </td>
                <td>{user.role}</td>
                <td>
                  <span className={`status-pill ${user.enabled ? "status-completed" : "status-draft"}`}>
                    {user.enabled ? "enabled" : "disabled"}
                  </span>
                </td>
                <td className="numeric">{user.deleted_at ?? "-"}</td>
                <td>
                  <div className="inline-actions">
                    <button className="btn btn-secondary btn-small" disabled={busyUserId === user.id} onClick={() => void handleToggle(user)} type="button">
                      {user.enabled ? "禁用" : "启用"}
                    </button>
                    <button className="btn btn-secondary btn-small" disabled={busyUserId === user.id} onClick={() => void handleReset(user)} type="button">
                      重置密码
                    </button>
                    <button className="btn btn-secondary btn-small" disabled={busyUserId === user.id} onClick={() => void handleDelete(user)} type="button">
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
