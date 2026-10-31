import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { useSignInResult } from "../components/SignInSteps";
import { ErrorNote, Field } from "../components/ui";
import { errorMessage, get, post } from "../lib/api";
import type { LoginResult } from "../lib/types";
import { AuthCard } from "./Login";

interface InvitationInfo {
  email: string;
  company_name: string;
  expires_at: string;
}

export function AcceptInvite() {
  const { token = "" } = useParams();
  const { handle, view } = useSignInResult();
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    get<InvitationInfo>(`/invitations/${token}`).then(setInfo).catch((e) => setError(errorMessage(e)));
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      handle(await post<LoginResult>(`/invitations/${token}/accept`, { full_name: fullName, password }));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (view) return <AuthCard>{view}</AuthCard>;
  return (
    <AuthCard>
      <h2>Accept your invitation</h2>
      {!info ? (
        <ErrorNote message={error} />
      ) : (
        <form className="stack" onSubmit={submit}>
          <p className="muted">
            You're joining <strong>{info.company_name}</strong> as <strong>{info.email}</strong>.
          </p>
          <Field label="Full name">
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required autoFocus />
          </Field>
          <Field label="Choose a password" hint="At least 10 characters.">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              minLength={10} required autoComplete="new-password" />
          </Field>
          <ErrorNote message={error} />
          <button className="primary">Continue</button>
        </form>
      )}
    </AuthCard>
  );
}
