import { PageHeader } from "../../components/ui";
import { useAuth } from "../../lib/auth";
import { ROLE_LABELS } from "../../lib/types";

export function Home() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <>
      <PageHeader title={`Welcome, ${user.full_name || user.email}`} />
      <div className="panel stack">
        <p>
          You're signed in to <strong>{user.company?.name}</strong> as{" "}
          {user.roles.map((r) => ROLE_LABELS[r]).join(", ")}.
        </p>
        <p className="muted">
          Chat with verified, persona-locked assistants arrives in the next phase. For now this workspace covers
          your team, sign-in security, and the tamper-evident audit log.
        </p>
      </div>
    </>
  );
}
