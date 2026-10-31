export type Role = "company_admin" | "analyst" | "reviewer" | "viewer";

export interface Me {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
  roles: Role[];
  company: { id: string; name: string; slug: string } | null;
}

export interface LoginResult {
  status: "ok" | "mfa_required" | "mfa_setup_required";
  user?: Me;
  mfa_token?: string;
  methods?: string[];
  recovery_codes?: string[];
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  status: "active" | "suspended";
  limits: { max_users: number; max_documents: number; queries_per_day: number };
  strictness: string;
  share_labels: boolean;
  created_at: string;
  user_count: number;
}

export interface CompanyUser {
  id: string;
  email: string;
  full_name: string;
  roles: Role[];
  status: "invited" | "active" | "deactivated";
  last_login_at: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  actor_user_id: string | null;
  actor_type: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  hash: string;
}

export interface AuditPage {
  items: AuditEntry[];
  next_cursor: number | null;
}

export interface Verification {
  valid: boolean;
  entries_checked: number;
  first_broken_id: number | null;
  reason: string | null;
}

export interface MfaMethod {
  id: string;
  type: "totp" | "email_otp" | "passkey";
  label: string;
  created_at: string;
  last_used_at: string | null;
}

export const ROLE_LABELS: Record<Role, string> = {
  company_admin: "Company Admin",
  analyst: "Analyst",
  reviewer: "Reviewer",
  viewer: "Viewer",
};
