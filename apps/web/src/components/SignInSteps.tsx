import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage, post } from "../lib/api";
import { homePath, useAuth } from "../lib/auth";
import type { LoginResult, Me } from "../lib/types";
import { MfaSetup } from "./MfaSetup";
import { ErrorNote, Field } from "./ui";

/** Everything after the first factor: second-factor check, setup, recovery codes. */
export function useSignInResult() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [pending, setPending] = useState<LoginResult | null>(null);
  const [codes, setCodes] = useState<{ codes: string[]; user: Me } | null>(null);

  function finish(user: Me) {
    setUser(user);
    navigate(homePath(user), { replace: true });
  }

  function handle(result: LoginResult) {
    if (result.status === "ok" && result.user) {
      if (result.recovery_codes?.length) setCodes({ codes: result.recovery_codes, user: result.user });
      else finish(result.user);
      return;
    }
    setPending(result);
  }

  let view = null;
  if (codes) {
    view = <RecoveryCodes codes={codes.codes} onContinue={() => finish(codes.user)} />;
  } else if (pending?.status === "mfa_required") {
    view = <MfaVerify result={pending} onResult={handle} />;
  } else if (pending?.status === "mfa_setup_required") {
    view = (
      <>
        <h2>Set up your second factor</h2>
        <MfaSetup mfaToken={pending.mfa_token} onDone={handle} />
      </>
    );
  }
  return { handle, view };
}

function MfaVerify({ result, onResult }: { result: LoginResult; onResult: (r: LoginResult) => void }) {
  const methods = result.methods ?? [];
  const [method, setMethod] = useState(methods[0] ?? "recovery_code");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendEmail() {
    setError(null);
    try {
      await post("/auth/mfa/email/send", { mfa_token: result.mfa_token });
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      onResult(await post<LoginResult>("/auth/mfa/verify", { mfa_token: result.mfa_token, method, code }));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const labels: Record<string, string> = {
    totp: "Authenticator app", email_otp: "Email code", recovery_code: "Recovery code" };
  return (
    <form className="stack" onSubmit={submit}>
      <h2>Second step</h2>
      <div className="tabs">
        {[...methods, "recovery_code"].map((m) => (
          <button type="button" key={m} className={m === method ? "tab active" : "tab"}
            onClick={() => { setMethod(m); setCode(""); }}>
            {labels[m] ?? m}
          </button>
        ))}
      </div>
      {method === "email_otp" && (
        <button type="button" className="secondary" onClick={sendEmail}>
          {sent ? "Send a new code" : "Email me a code"}
        </button>
      )}
      <Field label={method === "recovery_code" ? "Recovery code" : "6-digit code"}>
        <input value={code} onChange={(e) => setCode(e.target.value)} required autoFocus
          autoComplete="one-time-code" />
      </Field>
      {method === "recovery_code" && (
        <p className="muted small">After using a recovery code you'll set up a new second factor.</p>
      )}
      <ErrorNote message={error} />
      <button className="primary">Verify</button>
    </form>
  );
}

export function RecoveryCodes({ codes, onContinue }: { codes: string[]; onContinue: () => void }) {
  return (
    <div className="stack">
      <h2>Save your recovery codes</h2>
      <p className="muted">
        If you lose access to your second factor, each code signs you in once. They won't be shown again.
      </p>
      <ul className="codes">{codes.map((c) => <li key={c}>{c}</li>)}</ul>
      <button className="secondary" type="button"
        onClick={() => navigator.clipboard?.writeText(codes.join("\n"))}>Copy</button>
      <button className="primary" type="button" onClick={onContinue}>I've saved them</button>
    </div>
  );
}

export function PasswordForm({ onResult }: { onResult: (r: LoginResult) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onResult(await post<LoginResult>("/auth/login", { email, password }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <Field label="Work email">
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
          autoComplete="username" />
      </Field>
      <Field label="Password">
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
          autoComplete="current-password" />
      </Field>
      <ErrorNote message={error} />
      <button className="primary" disabled={busy}>Sign in</button>
    </form>
  );
}

export function EmailCodeForm({ onResult }: { onResult: (r: LoginResult) => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function request(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await post("/auth/otp/request", { email });
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      onResult(await post<LoginResult>("/auth/otp/verify", { email, code }));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (!sent) {
    return (
      <form className="stack" onSubmit={request}>
        <Field label="Work email" hint="Admins sign in with a password and second factor instead.">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </Field>
        <ErrorNote message={error} />
        <button className="primary">Email me a code</button>
      </form>
    );
  }
  return (
    <form className="stack" onSubmit={verify}>
      <p className="muted">If {email} can sign in with a code, we've sent one. It expires in 10 minutes.</p>
      <Field label="6-digit code">
        <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" maxLength={6}
          required autoFocus autoComplete="one-time-code" />
      </Field>
      <ErrorNote message={error} />
      <button className="primary">Sign in</button>
      <button type="button" className="link" onClick={() => setSent(false)}>Use a different email</button>
    </form>
  );
}
