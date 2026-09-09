/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
  /** Omit in dev to use `/api/botflow` (Vite proxy). Omit in prod static deploy to use same-origin `/api/v1/...` (nginx must proxy `/api`). */
  readonly VITE_API_BASE_URL?: string;
  /** Same value as API ``PORTAL_ADMIN_API_KEY`` — required for admin/onboarding API when not using Supabase JWT on the backend */
  readonly VITE_ADMIN_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
