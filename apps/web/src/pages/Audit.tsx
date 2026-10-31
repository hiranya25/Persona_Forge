import { useCallback, useEffect, useState } from "react";
import { Badge, ErrorNote, PageHeader, formatDate } from "../components/ui";
import { errorMessage, get, post } from "../lib/api";
import type { AuditEntry, AuditPage, Verification } from "../lib/types";

export function Audit({ scope }: { scope: "platform" | "company" }) {
  const base = scope === "platform" ? "/admin/audit" : "/audit";
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (before: number | null) => {
    try {
      const page = await get<AuditPage>(`${base}?limit=50${before ? `&cursor=${before}` : ""}`);
      setEntries((prev) => (before ? [...prev, ...page.items] : page.items));
      setCursor(page.next_cursor);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [base]);

  useEffect(() => {
    load(null);
  }, [load]);

  async function verify() {
    try {
      setVerification(await post<Verification>(`${base}/verify`));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <>
      <PageHeader title={scope === "platform" ? "Platform audit log" : "Audit log"}>
        <button className="secondary" onClick={verify}>Verify integrity</button>
      </PageHeader>
      {verification && (
        <p className={verification.valid ? "notice ok" : "notice warn"}>
          {verification.valid
            ? `Chain intact — ${verification.entries_checked} entries verified.`
            : `Chain broken at entry #${verification.first_broken_id}: ${verification.reason}`}
        </p>
      )}
      <ErrorNote message={error} />
      <table>
        <thead>
          <tr><th>#</th><th>When</th><th>Action</th><th>Details</th><th>Hash</th></tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td className="mono">{e.id}</td>
              <td>{formatDate(e.created_at)}</td>
              <td><Badge>{e.action}</Badge></td>
              <td className="small mono">{Object.keys(e.payload).length ? JSON.stringify(e.payload) : "—"}</td>
              <td className="mono small" title={e.hash}>{e.hash.slice(0, 10)}…</td>
            </tr>
          ))}
        </tbody>
      </table>
      {cursor && <button className="secondary" onClick={() => load(cursor)}>Load older entries</button>}
    </>
  );
}
