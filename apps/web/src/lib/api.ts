// Thin fetch wrapper: same-origin cookies, CSRF double-submit, one silent refresh on 401.

export class ApiError extends Error {
  constructor(
    public status: number,
    public title: string,
    public detail: string | null,
    public body: unknown,
  ) {
    super(detail ?? title);
  }
}

export function readCookie(name: string, cookies: string = document.cookie): string | null {
  for (const part of cookies.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export function buildHeaders(method: string, hasBody: boolean, cookies?: string): Headers {
  const headers = new Headers();
  if (hasBody) headers.set("Content-Type", "application/json");
  const csrf = readCookie("pf_csrf", cookies);
  if (csrf && method !== "GET") headers.set("X-CSRF-Token", csrf);
  return headers;
}

let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: buildHeaders("POST", false),
  })
    .then((r) => r.ok)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

const NO_REFRESH = ["/auth/login", "/auth/refresh", "/auth/otp/", "/auth/mfa/verify"];

export async function api<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: buildHeaders(method, body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401 && retry && !NO_REFRESH.some((p) => path.startsWith(p))) {
    if (await refreshSession()) return api<T>(method, path, body, false);
  }
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new ApiError(response.status, problem.title ?? response.statusText, problem.detail ?? null, problem);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const get = <T>(path: string) => api<T>("GET", path);
export const post = <T>(path: string, body?: unknown) => api<T>("POST", path, body ?? {});
export const patch = <T>(path: string, body: unknown) => api<T>("PATCH", path, body);
export const del = <T>(path: string) => api<T>("DELETE", path);

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const fields = (error.body as { errors?: { loc: string[]; msg: string }[] })?.errors;
    if (fields?.length) return fields.map((f) => `${f.loc.at(-1)}: ${f.msg}`).join(" · ");
    return error.detail ?? error.title;
  }
  return "Something went wrong. Please try again.";
}
