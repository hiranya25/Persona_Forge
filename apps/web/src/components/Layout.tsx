import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { hasRole, useAuth } from "../lib/auth";
import { ROLE_LABELS } from "../lib/types";

interface NavItem {
  to: string;
  label: string;
  show: boolean;
}

export function Layout({ portal }: { portal: "admin" | "company" }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;

  const items: NavItem[] =
    portal === "admin"
      ? [
          { to: "/admin/companies", label: "Companies", show: true },
          { to: "/admin/audit", label: "Platform audit log", show: true },
          { to: "/admin/account", label: "Account & security", show: true },
        ]
      : [
          { to: "/app", label: "Home", show: true },
          { to: "/app/users", label: "Users", show: hasRole(user, "company_admin") },
          { to: "/app/audit", label: "Audit log", show: hasRole(user, "company_admin", "reviewer", "viewer") },
          { to: "/app/account", label: "Account & security", show: true },
        ];

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">PERSONA_FORGE</div>
        <div className="org">{portal === "admin" ? "Platform admin" : user.company?.name}</div>
        <nav>
          {items.filter((i) => i.show).map((i) => (
            <NavLink key={i.to} to={i.to} end className={({ isActive }) => (isActive ? "nav active" : "nav")}>
              {i.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <div>
            <strong>{user.full_name || user.email}</strong>
            <span className="muted small">
              {" · "}
              {user.is_platform_admin ? "Platform Admin" : user.roles.map((r) => ROLE_LABELS[r]).join(", ")}
            </span>
          </div>
          <button className="link" onClick={handleSignOut}>Sign out</button>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
