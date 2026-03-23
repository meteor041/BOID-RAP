import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function AdminGate({ children }: PropsWithChildren) {
  const { user } = useAuth();

  if (user?.role !== "admin") {
    return <Navigate to="/workspace" replace />;
  }

  return <>{children}</>;
}
