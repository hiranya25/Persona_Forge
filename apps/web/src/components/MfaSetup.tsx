import QRCode from "qrcode";
import { useState, type FormEvent } from "react";
import { errorMessage, post } from "../lib/api";
import type { LoginResult } from "../lib/types";
import { ErrorNote, Field } from "./ui";

interface Props {
  /** Present mid-sign-in; absent when adding a method from the Account page. */
  mfaToken?: string;
  onDone: (result: LoginResult) => void;
}

type Step =
  | { kind: "choose" }
  | { kind: "totp"; methodId: string; secret: string; qr: string }
  | { kind: "email"; methodId: string };

export function MfaSetup({ mfaToken, onDone }: Props) {
  const [step, setStep] = useState<Step>({ kind: "choose" });
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function startTotp() {
    setError(null);
    try {
      const r = await post<{ method_id: string; secret: string; otpauth_uri: string }>(
        "/auth/mfa/setup/totp/start", { mfa_token: mfaToken });
      setStep({ kind: "totp", methodId: r.method_id, secret: r.secret, qr: await QRCode.toDataURL(r.otpauth_uri) });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function startEmail() {
    setError(null);
    try {
      const r = await post<{ method_id: string }>("/auth/mfa/setup/email/start", { mfa_token: mfaToken });
      setStep({ kind: "email", methodId: r.method_id });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (step.kind === "choose") return;
    setBusy(true);
    setError(null);
    try {
      onDone(await post<LoginResult>("/auth/mfa/setup/confirm", {
        mfa_token: mfaToken, method_id: step.methodId, code }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (step.kind === "choose") {
    return (
      <div className="stack">
        <p className="muted">Admin accounts need a second step at sign-in. Choose one:</p>
        <button className="option" onClick={startTotp}>
          <strong>Authenticator app</strong>
          <span>Google Authenticator, 1Password, Authy, or similar.</span>
        </button>
        <button className="option" onClick={startEmail}>
          <strong>Email code</strong>
          <span>We email you a 6-digit code each time you sign in.</span>
        </button>
        <ErrorNote message={error} />
      </div>
    );
  }

  return (
    <form className="stack" onSubmit={confirm}>
      {step.kind === "totp" ? (
        <>
          <p className="muted">Scan this QR code with your authenticator app, then enter the 6-digit code it shows.</p>
          <img className="qr" src={step.qr} alt="QR code for your authenticator app" />
          <p className="mono small">Can't scan? Enter this key: {step.secret}</p>
        </>
      ) : (
        <p className="muted">We sent a 6-digit code to your email. Enter it to confirm.</p>
      )}
      <Field label="Code">
        <input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric"
          autoComplete="one-time-code" maxLength={6} required autoFocus />
      </Field>
      <ErrorNote message={error} />
      <button className="primary" disabled={busy}>Confirm</button>
    </form>
  );
}
