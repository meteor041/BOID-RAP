import { Navigate, createBrowserRouter } from "react-router-dom";
import { AdminGate } from "../features/auth/AdminGate";
import { AuthGate } from "../features/auth/AuthGate";
import { AppShell } from "../components/layout/AppShell";
import { AdminModelsPage } from "../pages/AdminModelsPage/AdminModelsPage";
import { AdminUsersPage } from "../pages/AdminUsersPage/AdminUsersPage";
import { AuditLogsPage } from "../pages/AuditLogsPage/AuditLogsPage";
import { JobPage } from "../pages/JobPage/JobPage";
import { LoginPage } from "../pages/LoginPage/LoginPage";
import { ReportDetailPage } from "../pages/ReportDetailPage/ReportDetailPage";
import { ReportsPage } from "../pages/ReportsPage/ReportsPage";
import { SearchInsightsPage } from "../pages/SearchInsightsPage/SearchInsightsPage";
import { SessionDetailPage } from "../pages/SessionDetailPage/SessionDetailPage";
import { WorkspacePage } from "../pages/WorkspacePage/WorkspacePage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/workspace" replace />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: (
      <AuthGate>
        <AppShell />
      </AuthGate>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/workspace" replace />,
      },
      {
        path: "workspace",
        element: <WorkspacePage />,
      },
      {
        path: "workspace/sessions/:sessionId",
        element: <SessionDetailPage />,
      },
      {
        path: "jobs/:jobId",
        element: <JobPage />,
      },
      {
        path: "admin/users",
        element: (
          <AdminGate>
            <AdminUsersPage />
          </AdminGate>
        ),
      },
      {
        path: "admin/models",
        element: (
          <AdminGate>
            <AdminModelsPage />
          </AdminGate>
        ),
      },
      {
        path: "admin/audit-logs",
        element: (
          <AdminGate>
            <AuditLogsPage />
          </AdminGate>
        ),
      },
      {
        path: "reports",
        element: <ReportsPage />,
      },
      {
        path: "reports/:reportId",
        element: <ReportDetailPage />,
      },
      {
        path: "search-insights",
        element: <SearchInsightsPage />,
      },
    ],
  },
]);
