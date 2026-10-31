import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { homePath, useAuth } from "./lib/auth";
import { Account } from "./pages/Account";
import { AcceptInvite } from "./pages/AcceptInvite";
import { Audit } from "./pages/Audit";
import { Login } from "./pages/Login";
import { Companies } from "./pages/admin/Companies";
import { Home } from "./pages/company/Home";
import { Users } from "./pages/company/Users";

function RequireAuth({ portal, children }: { portal: "admin" | "company"; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="loading">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  // Each portal is only for its own kind of user; the API enforces this too.
  if ((portal === "admin") !== user.is_platform_admin) return <Navigate to={homePath(user)} replace />;
  return <>{children}</>;
}

export function App() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      <Route path="/admin" element={<RequireAuth portal="admin"><Layout portal="admin" /></RequireAuth>}>
        <Route index element={<Navigate to="companies" replace />} />
        <Route path="companies" element={<Companies />} />
        <Route path="audit" element={<Audit scope="platform" />} />
        <Route path="account" element={<Account />} />
      </Route>
      <Route path="/app" element={<RequireAuth portal="company"><Layout portal="company" /></RequireAuth>}>
        <Route index element={<Home />} />
        <Route path="users" element={<Users />} />
        <Route path="audit" element={<Audit scope="company" />} />
        <Route path="account" element={<Account />} />
      </Route>
      <Route path="*" element={
        loading ? <p className="loading">Loading…</p> : <Navigate to={user ? homePath(user) : "/login"} replace />
      } />
    </Routes>
  );
}
