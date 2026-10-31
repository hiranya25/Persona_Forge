import { useEffect, useState, type FormEvent } from "react";
import { Badge, ErrorNote, Field, PageHeader, formatDate } from "../../components/ui";
import { errorMessage, get, patch, post } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ROLE_LABELS, type CompanyUser, type Role } from "../../lib/types";

const ROLES = Object.keys(ROLE_LABELS) as Role[];

export function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<CompanyUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", roles: ["analyst"] as Role[] });

  const load = () => get<CompanyUser[]>("/users").then(setUsers).catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    load();
  }, []);

  function toggleRole(role: Role) {
    setForm((f) => ({
      ...f, roles: f.roles.includes(role) ? f.roles.filter((r) => r !== role) : [...f.roles, role] }));
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await post("/users", form);
      setMessage(`Account created for ${form.email}. Share the initial password with them securely.`);
      setForm({ email: "", full_name: "", password: "", roles: ["analyst"] });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function setStatus(user: CompanyUser, status: "active" | "deactivated") {
    setError(null);
    try {
      await patch(`/users/${user.id}`, { status });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function resetPassword(user: CompanyUser) {
    const password = window.prompt(`New password for ${user.email} (at least 10 characters):`);
    if (!password) return;
    setError(null);
    try {
      await post(`/users/${user.id}/reset-password`, { password });
      setMessage(`Password reset for ${user.email}. Their existing sessions were signed out.`);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <>
      <PageHeader title="Users" />
      <form className="panel stack" onSubmit={create}>
        <h2>Add a user</h2>
        <div className="grid-2">
          <Field label="Email">
            <input type="email" value={form.email} required
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <Field label="Full name">
            <input value={form.full_name} required
              onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Field>
          <Field label="Initial password" hint="At least 10 characters. They can change it later.">
            <input type="password" value={form.password} minLength={10} required autoComplete="new-password"
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field>
          <fieldset className="roles">
            <legend className="field-label">Roles</legend>
            {ROLES.map((r) => (
              <label key={r} className="check">
                <input type="checkbox" checked={form.roles.includes(r)} onChange={() => toggleRole(r)} />
                {ROLE_LABELS[r]}
              </label>
            ))}
          </fieldset>
        </div>
        <button className="primary" disabled={!form.roles.length}>Create user</button>
      </form>
      {message && <p className="notice ok">{message}</p>}
      <ErrorNote message={error} />
      <table>
        <thead>
          <tr><th>User</th><th>Roles</th><th>Status</th><th>Last sign-in</th><th /></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td><strong>{u.full_name}</strong><div className="muted small">{u.email}</div></td>
              <td>{u.roles.map((r) => ROLE_LABELS[r]).join(", ")}</td>
              <td><Badge tone={u.status === "active" ? "ok" : "warn"}>{u.status}</Badge></td>
              <td>{formatDate(u.last_login_at)}</td>
              <td className="row-actions">
                {u.id !== me?.id && u.status === "active" && (
                  <button className="link" onClick={() => setStatus(u, "deactivated")}>Deactivate</button>
                )}
                {u.status === "deactivated" && (
                  <button className="link" onClick={() => setStatus(u, "active")}>Reactivate</button>
                )}
                {u.id !== me?.id && u.status !== "invited" && (
                  <button className="link" onClick={() => resetPassword(u)}>Reset password</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
