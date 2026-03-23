import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell fade-in">
      <aside className="app-sidebar">
        <div className="brand-block">
          <p className="eyebrow">BOID-RAP</p>
          <h1 className="sidebar-title">Research Terminal</h1>
          <p className="sidebar-copy">
            面向公司、股票与商品研究的智能分析工作台。
          </p>
        </div>

        <nav className="sidebar-nav">
          <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}`} to="/workspace">
            调研工作台
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}`} to="/reports">
            报告中心
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}`} to="/search-insights">
            搜索洞察
          </NavLink>
          {user?.role === "admin" ? (
            <>
              <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}`} to="/admin/users">
                用户管理
              </NavLink>
              <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}`} to="/admin/models">
                模型管理
              </NavLink>
              <NavLink className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}`} to="/admin/audit-logs">
                审计日志
              </NavLink>
            </>
          ) : null}
        </nav>

        <div className="sidebar-meta">
          <p className="meta-label">当前用户</p>
          <p className="meta-value">{user?.username ?? "未登录"}</p>
          <p className="meta-label">角色</p>
          <p className="meta-value numeric">{user?.role ?? "-"}</p>
          <button className="btn btn-secondary sidebar-action" onClick={logout} type="button">
            退出登录
          </button>
        </div>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
