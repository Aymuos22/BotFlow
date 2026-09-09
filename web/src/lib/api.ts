/**
 * Base URL for FastAPI.
 *
 * - **Production / preview:** usually `""` so requests are same-origin (nginx / Vercel proxy).
 * - **Local dev:** defaults to `http://127.0.0.1:8000` (direct to uvicorn). The API allows
 *   `http://localhost:5173` in CORS when `APP_ENV` is not `production`. This avoids flaky
 *   Vite proxy 404s on `GET /api/botflow/api/v1/...`.
 * - Override with `VITE_API_BASE_URL` (e.g. `/api/botflow` to force the Vite proxy).
 */
export function apiBase(): string {
  const raw = (import.meta.env.VITE_API_BASE_URL ?? "").trim();
  if (raw) return raw.replace(/\/$/, "");
  if (import.meta.env.DEV) {
    return "http://127.0.0.1:8000";
  }
  return "";
}

/** Authorization + optional X-Admin-Key for API calls (JSON or multipart). */
export function authHeadersForFetch(accessToken: string): Record<string, string> {
  const key = (
    import.meta.env.VITE_ADMIN_API_KEY as string | undefined
  )?.trim();
  return {
    Authorization: `Bearer ${accessToken}`,
    ...(key ? { "X-Admin-Key": key } : {}),
  };
}

type ApiOk<T> = { success: true; data: T; message?: string };
type ApiErr = { success: false; error: string; code?: string };

function apiErrorMessage(body: unknown, status: number): string {
  if (!body || typeof body !== "object") return `HTTP ${status}`;

  const b = body as {
    error?: unknown;
    detail?: unknown;
    message?: unknown;
  };
  if (typeof b.error === "string" && b.error) return b.error;
  if (typeof b.message === "string" && b.message) return b.message;
  if (typeof b.detail === "string" && b.detail) return b.detail;
  if (Array.isArray(b.detail)) {
    const messages = b.detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const err = item as { loc?: unknown; msg?: unknown };
        const msg = typeof err.msg === "string" ? err.msg : null;
        if (!msg) return null;
        const loc = Array.isArray(err.loc)
          ? err.loc.filter((part) => part !== "body").join(" -> ")
          : "";
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter((msg): msg is string => Boolean(msg));
    if (messages.length > 0) return messages.join("; ");
  }
  return `HTTP ${status}`;
}

export async function apiFetch<T>(
  path: string,
  accessToken: string,
  init?: RequestInit,
): Promise<T> {
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      ...authHeadersForFetch(accessToken),
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok || !body || typeof body !== "object") {
    throw new Error(apiErrorMessage(body, res.status));
  }
  const b = body as ApiOk<T> | ApiErr | { detail?: string };
  if ("success" in b && b.success === false) {
    throw new Error((b as ApiErr).error || "Request failed");
  }
  if ("success" in b && b.success && "data" in b) {
    return (b as ApiOk<T>).data;
  }
  if ("detail" in b && typeof b.detail === "string") {
    throw new Error(b.detail);
  }
  throw new Error("Unexpected response shape");
}

export type CompanySummary = {
  id: string;
  name: string;
  display_name: string;
  status: string;
};

export type PortalLoginUser = {
  id: string;
  username: string;
  role: "admin" | "user";
  company_id: string | null;
  is_active: boolean;
};

export type PortalLoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: PortalLoginUser;
};

export async function portalLogin(
  username: string,
  password: string,
): Promise<PortalLoginResponse> {
  const res = await fetch(`${apiBase()}/api/v1/portal/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok || !body || typeof body !== "object") {
    throw new Error(apiErrorMessage(body, res.status));
  }
  const b = body as ApiOk<PortalLoginResponse> | ApiErr | { detail?: string };
  if ("success" in b && b.success && "data" in b) return b.data;
  if ("success" in b && b.success === false) {
    throw new Error((b as ApiErr).error || "Invalid username or password.");
  }
  if ("detail" in b && typeof b.detail === "string") throw new Error(b.detail);
  throw new Error("Unexpected response shape");
}

export async function listCompanies(token: string): Promise<CompanySummary[]> {
  return apiFetch<CompanySummary[]>("/api/v1/portal/admin/companies", token);
}

/** Row from GET /api/v1/meta/languages (no auth). */
export type LanguageOption = {
  code: string;
  label: string;
  description: string;
};

/**
 * Languages the backend accepts for `supported_languages` / `default_language`.
 * Public endpoint — same catalog as portal config overview `language_catalog`.
 */
export async function getLanguageCatalog(): Promise<LanguageOption[]> {
  const res = await fetch(`${apiBase()}/api/v1/meta/languages`, {
    headers: { Accept: "application/json" },
  });
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok || !body || typeof body !== "object") {
    throw new Error(`HTTP ${res.status}`);
  }
  const b = body as { success?: boolean; data?: LanguageOption[] };
  if (!b.success || !Array.isArray(b.data)) {
    throw new Error("Unexpected language catalog response");
  }
  return b.data;
}

export type OnboardBody = {
  company_name: string;
  display_name: string;
  phone_number: string;
  default_language?: string;
  supported_languages?: string[];
};

export async function fullOnboard(
  token: string,
  body: OnboardBody,
): Promise<unknown> {
  return apiFetch("/api/v1/onboarding/company/full", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type RagSourceItem = {
  file_name: string;
  document_id?: string | null;
  chunk_index?: number | null;
  score?: number | null;
};

export type ChatReply = {
  answer: string;
  response_type: string;
  language: string;
  detected_language: string;
  top_score?: number | null;
  sources?: RagSourceItem[] | null;
};

export type PortalChatTurn = {
  role: "user" | "assistant";
  content: string;
};

export async function portalChat(
  token: string,
  companyId: string,
  message: string,
  history?: PortalChatTurn[],
): Promise<ChatReply> {
  const body: Record<string, unknown> = { company_id: companyId, message };
  if (history && history.length > 0) {
    body.history = history;
  }
  return apiFetch<ChatReply>("/api/v1/portal/chat", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
