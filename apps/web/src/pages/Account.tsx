import { useCallback, useEffect, useState, type FormEvent } from "react";
import { MfaSetup } from "../components/MfaSetup";
import { RecoveryCodes } from "../components/SignInSteps";
import { ErrorNote, Field, PageHeader, formatDate } from "../components/ui";
import { del, errorMessage, get, post } from "../lib/api";
import { hasRole, useAuth } from "../lib/auth";
import type { LoginResult, MfaMethod } from "../lib/types";

export function Account() {
  const { user } = useAuth();
  const isAdmin = !!user && (user.is_platform_admin || hasRole(user, "company_admin"));
  return (
    <>
      <PageHeader title="Account & security" />
      <ChangePassword />
      {isAdmin && <SecondFactors />}
    </>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setDone(false);
    try {
      await post("/me/password", { current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setDone(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>Password</h2>
      <div className="grid-2">
        <Field label="Current password">
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required
            autoComplete="current-password" />
        </Field>
        <Field label="New password" hint="At least 10 characters.">
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} minLength={10} required
            autoComplete="new-password" />
        </Field>
      </div>
      <ErrorNote message={error} />
      {done && <p className="notice ok">Password changed.</p>}
      <button className="primary">Change password</button>
    </form>
  );
}

function SecondFactors() {
  const [methods, setMethods] = useState<MfaMethod[]>([]);
  const [adding, setAdding] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => get<MfaMethod[]>("/me/mfa-methods").then(setMethods), []);
  useEffect(() => {
    load();
  }, [load]);

  async function remove(method: MfaMethod) {
    setError(null);
    try {
      await del(`/me/mfa-methods/${method.id}`);
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function regenerate() {
    if (!window.confirm("Replace your recovery codes? The old ones stop working.")) return;
    setCodes((await post<{ recovery_codes: string[] }>("/me/recovery-codes")).recovery_codes);
  }

  function added(result: LoginResult) {
    setAdding(false);
    if (result.recovery_codes) setCodes(result.recovery_codes);
    load();
  }

  if (codes) return <div className="panel"><RecoveryCodes codes={codes} onContinue={() => setCodes(null)} /></div>;
  return (
    <div className="panel stack">
      <h2>Second factors</h2>
      <table>
        <thead><tr><th>Method</th><th>Added</th><th>Last used</th><th /></tr></thead>
        <tbody>
          {methods.map((m) => (
            <tr key={m.id}>
              <td>{m.label}</td>
              <td>{formatDate(m.created_at)}</td>
              <td>{formatDate(m.last_used_at)}</td>
              <td className="row-actions"><button className="link" onClick={() => remove(m)}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <ErrorNote message={error} />
      {adding ? (
        <MfaSetup onDone={added} />
      ) : (
        <div className="row">
          <button className="secondary" onClick={() => setAdding(true)}>Add a second factor</button>
          <button className="secondary" onClick={regenerate}>New recovery codes</button>
        </div>
      )}
    </div>
  );
}
