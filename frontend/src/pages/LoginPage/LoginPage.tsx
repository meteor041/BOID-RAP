import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import { login } from "../../services/auth";
import type { ApiError } from "../../services/http";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login: setLogin, isAuthenticated } = useAuth();
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("analyst123");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? "/workspace";

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [from, isAuthenticated, navigate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = await login({ username, password });
      setLogin(payload);
      navigate(from, { replace: true });
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page fade-in">
      <section className="login-panel card">
        <div className="login-copy">
          <p className="eyebrow">BOID-RAP</p>
          <h1 className="page-title">金融研究工作台</h1>
          <p className="page-subtitle">
            专业、克制的信息界面。用于调研公司、股票与商品，并沉淀结构化研究结果。
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="form-field">
            <span className="form-label">用户名</span>
            <input
              autoComplete="username"
              className="input"
              onChange={(event) => setUsername(event.target.value)}
              value={username}
            />
          </label>

          <label className="form-field">
            <span className="form-label">密码</span>
            <input
              autoComplete="current-password"
              className="input numeric"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>

          {error ? <p className="form-error">{error}</p> : null}

          <div className="login-actions">
            <button className="btn btn-primary" disabled={submitting} type="submit">
              {submitting ? "登录中..." : "进入工作台"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
