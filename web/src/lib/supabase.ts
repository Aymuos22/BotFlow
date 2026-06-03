import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !anon) {
  console.warn(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY — set them in web/.env",
  );
}

export const supabase = createClient(url ?? "", anon ?? "");

export type AppRole = "admin" | "user";

export function appRoleFromUser(user: {
  app_metadata?: Record<string, unknown>;
}): AppRole | null {
  const r = user.app_metadata?.role;
  return r === "admin" || r === "user" ? r : null;
}

export function companyIdFromUser(user: {
  app_metadata?: Record<string, unknown>;
}): string | null {
  const cid = user.app_metadata?.company_id;
  return typeof cid === "string" && cid.length > 0 ? cid : null;
}
