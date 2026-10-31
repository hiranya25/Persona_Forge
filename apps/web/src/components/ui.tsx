import type { ReactNode } from "react";

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  return message ? <p className="error" role="alert">{message}</p> : null;
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      <div className="page-actions">{children}</div>
    </div>
  );
}

export function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "—";
}
