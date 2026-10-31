import { useEffect, useState, type FormEvent } from "react";
import { Badge, ErrorNote, Field, PageHeader, formatDate } from "../../components/ui";
import { errorMessage, get, patch, post } from "../../lib/api";
import type { Company } from "../../lib/types";

export function Companies() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [name, setName] = useState("");
  const [maxUsers, setMaxUsers] = useState(25);
  const [inviteFor, setInviteFor] = useState<Company | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => get<Company[]>("/admin/companies").then(setCompanies).catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    load();
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await post("/admin/companies", {
        name, limits: { max_users: maxUsers, max_documents: 500, queries_per_day: 500 } });
      setName("");
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function invite(event: FormEvent) {
    event.preventDefault();
    if (!inviteFor) return;
    setError(null);
    try {
      await post(`/admin/companies/${inviteFor.id}/invite-admin`, { email: inviteEmail });
      setMessage(`Invitation sent to ${inviteEmail}.`);
      setInviteFor(null);
      setInviteEmail("");
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function toggleStatus(company: Company) {
    setError(null);
    try {
      await patch(`/admin/companies/${company.id}`, {
        status: company.status === "active" ? "suspended" : "active" });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <>
      <PageHeader title="Companies" />
      <form className="inline-form" onSubmit={create}>
        <Field label="New company name">
          <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
        </Field>
        <Field label="Max users">
          <input type="number" min={1} value={maxUsers} onChange={(e) => setMaxUsers(Number(e.target.value))} />
        </Field>
        <button className="primary">Create company</button>
      </form>
      {inviteFor && (
        <form className="inline-form panel" onSubmit={invite}>
          <Field label={`Invite the Company Admin for ${inviteFor.name}`}>
            <input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required
              autoFocus placeholder="admin@company.com" />
          </Field>
          <button className="primary">Send invitation</button>
          <button type="button" className="link" onClick={() => setInviteFor(null)}>Cancel</button>
        </form>
      )}
      {message && <p className="notice ok">{message}</p>}
      <ErrorNote message={error} />
      <table>
        <thead>
          <tr><th>Company</th><th>Status</th><th>Users</th><th>Created</th><th /></tr>
        </thead>
        <tbody>
          {companies.map((c) => (
            <tr key={c.id}>
              <td><strong>{c.name}</strong><div className="muted small mono">{c.slug}</div></td>
              <td><Badge tone={c.status === "active" ? "ok" : "warn"}>{c.status}</Badge></td>
              <td>{c.user_count} / {c.limits.max_users}</td>
              <td>{formatDate(c.created_at)}</td>
              <td className="row-actions">
                <button className="link" onClick={() => { setInviteFor(c); setMessage(null); }}>Invite admin</button>
                <button className="link" onClick={() => toggleStatus(c)}>
                  {c.status === "active" ? "Suspend" : "Reactivate"}
                </button>
              </td>
            </tr>
          ))}
          {!companies.length && <tr><td colSpan={5} className="muted">No companies yet.</td></tr>}
        </tbody>
      </table>
    </>
  );
}
