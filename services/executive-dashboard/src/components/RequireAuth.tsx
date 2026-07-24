import { Navigate, Outlet, useLocation } from "react-router-dom";
import { getToken } from "../lib/auth";

export function RequireAuth() {
  const location = useLocation();
  if (!getToken()) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <Outlet />;
}
