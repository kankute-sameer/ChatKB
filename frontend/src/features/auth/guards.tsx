import type { ReactNode } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthProvider";

export function RequireAuth() {
  const { username, ready } = useAuth();
  if (!ready) {
    return <div className="h-full bg-background" />;
  }
  if (!username) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

export function GuestOnly() {
  const { username, ready } = useAuth();
  if (!ready) {
    return <div className="h-full bg-background" />;
  }
  if (username) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

export function AliceOnly({ children }: { children: ReactNode }) {
  const { username, ready } = useAuth();
  if (!ready) {
    return <div className="h-full bg-background" />;
  }
  if (username !== "alice") {
    return <Navigate to="/" replace />;
  }
  return children;
}
