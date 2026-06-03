/**
 * Client bindings for admin / support APIs (companies, documents, handoffs, analytics, portal users).
 * Backend routes live under /api/v1/…
 */
import {
  apiBase,
  apiFetch,
  authHeadersForFetch,
  type LanguageOption,
} from "./api";

// ── Companies: lifecycle & config ──────────────────────────────────

export type WhatsAppProvider = "twilio" | "aisensy" | "meta";

export type CompanyConfig = {
  id: string;
  company_id: string;
  weaviate_collection: string;
  /** Active WhatsApp transport provider. */
  whatsapp_provider?: WhatsAppProvider | null;
  /** Per-company Twilio sender number in whatsapp:+<E.164> format, e.g. whatsapp:+14155238886. */
  twilio_whatsapp_number?: string | null;
  /** Per-company Twilio Account SID (ACxxxxxxxx…). */
  twilio_account_sid?: string | null;
  is_active: boolean;
  default_language: string;
  supported_languages: string[];
  system_prompt: string | null;
  rag_config_json: Record<string, unknown> | null;
  fallback_config_json: Record<string, unknown> | null;
  handoff_config_json: Record<string, unknown> | null;
  business_hours_json: Record<string, unknown> | null;
  whatsapp_agent_inactivity_minutes: number | null;
  /** Supervisor WhatsApp; receives handoff alerts. Accepts +E164 / digits; API stores whatsapp:+…. */
  handoff_staff_notify_whatsapp?: string | null;
  google_sheets_enabled?: boolean;
  google_sheet_id?: string | null;
  google_sheet_url?: string | null;
  /** True when an encrypted Twilio auth token is stored (read-only). */
  has_twilio_auth_token?: boolean;
  aisensy_whatsapp_number?: string | null;
  aisensy_project_id?: string | null;
  has_aisensy_api_key?: boolean;
  meta_phone_number_id?: string | null;
  meta_waba_id?: string | null;
  has_meta_graph_token?: boolean;
  has_meta_app_secret?: boolean;
  has_meta_webhook_verify_token?: boolean;
  created_at: string;
  updated_at: string;
};

export type CompanyConfigUpdate = Partial<{
  default_language: string;
  supported_languages: string[];
  system_prompt: string | null;
  rag_config_json: Record<string, unknown> | null;
  fallback_config_json: Record<string, unknown> | null;
  handoff_config_json: Record<string, unknown> | null;
  business_hours_json: Record<string, unknown> | null;
  whatsapp_agent_inactivity_minutes: number | null;
  whatsapp_provider: WhatsAppProvider;
  twilio_whatsapp_number: string | null;
  handoff_staff_notify_whatsapp: string | null;
  google_sheets_enabled: boolean;
  google_sheet_id: string | null;
  is_active: boolean;
  /** Preserve or switch the active transport (default twilio if omitted). */
  whatsapp_provider?: WhatsAppProvider;
  twilio_whatsapp_number?: string | null;
}>;

export async function getCompanyReadiness(
  token: string,
  companyId: string,
): Promise<unknown> {
  return apiFetch(`/api/v1/companies/${companyId}/readiness`, token);
}

export async function activateCompany(
  token: string,
  companyId: string,
): Promise<unknown> {
  return apiFetch(`/api/v1/companies/${companyId}/activate`, token, {
    method: "POST",
  });
}

export async function getCompanyConfig(
  token: string,
  companyId: string,
): Promise<CompanyConfig> {
  return apiFetch<CompanyConfig>(
    `/api/v1/portal/companies/${companyId}/config`,
    token,
  );
}

export type PortalRagDefaults = {
  score_threshold: number;
  top_k: number;
  hybrid_alpha: number;
  rag_embeddings_enabled: boolean;
  rag_conversation_turns: number;
  rag_augment_search_with_history: boolean;
};

export type PortalConfigOverview = {
  company_id: string;
  updated_at: string;
  prompt: {
    system_prompt: string | null;
    default_language: string;
    supported_languages: string[];
  };
  /** Same as GET /api/v1/meta/languages — UI labels for language pickers. */
  language_catalog?: LanguageOption[];
  rag: {
    rag_config_json: Record<string, unknown> | null;
    global_defaults: PortalRagDefaults;
  };
  escalation: {
    fallback_config_json: Record<string, unknown> | null;
    handoff_config_json: Record<string, unknown> | null;
    business_hours_json: Record<string, unknown> | null;
  };
  integration: {
    weaviate_collection: string;
    is_active: boolean;
    whatsapp_provider: string | null;
    twilio_whatsapp_number: string | null;
    twilio_account_sid: string | null;
    has_twilio_auth_token: boolean;
    /** True when handoff_staff_notify_whatsapp is set (new-handoff staff alerts). */
    handoff_staff_notify_configured?: boolean;
    twilio_credentials_complete?: boolean;
    whatsapp_channel_key?: string;
    twilio_credentials_save_path?: string;
    aisensy_whatsapp_number?: string | null;
    aisensy_project_id?: string | null;
    has_aisensy_api_key?: boolean;
    aisensy_credentials_complete?: boolean;
    aisensy_credentials_save_path?: string;
    meta_phone_number_id?: string | null;
    meta_waba_id?: string | null;
    has_meta_graph_token?: boolean;
    meta_credentials_complete?: boolean;
    meta_credentials_save_path?: string;
    /** Set when a primary WhatsApp channel row exists. */
    whatsapp_channel_key?: string | null;
  };
};

export async function getCompanyConfigOverview(
  token: string,
  companyId: string,
): Promise<PortalConfigOverview> {
  return apiFetch<PortalConfigOverview>(
    `/api/v1/portal/companies/${companyId}/config/overview`,
    token,
  );
}

export type PortalPromptConfig = {
  system_prompt: string | null;
  default_language: string;
  supported_languages: string[];
};

export async function getPortalPromptConfig(
  token: string,
  companyId: string,
): Promise<PortalPromptConfig> {
  return apiFetch<PortalPromptConfig>(
    `/api/v1/portal/companies/${companyId}/config/prompt`,
    token,
  );
}

export type PortalRagConfig = {
  rag_config_json: Record<string, unknown> | null;
  global_defaults: PortalRagDefaults;
};

export async function getPortalRagConfig(
  token: string,
  companyId: string,
): Promise<PortalRagConfig> {
  return apiFetch<PortalRagConfig>(
    `/api/v1/portal/companies/${companyId}/config/rag`,
    token,
  );
}

export type PortalEscalationConfig = {
  fallback_config_json: Record<string, unknown> | null;
  handoff_config_json: Record<string, unknown> | null;
  business_hours_json: Record<string, unknown> | null;
};

export async function getPortalEscalationConfig(
  token: string,
  companyId: string,
): Promise<PortalEscalationConfig> {
  return apiFetch<PortalEscalationConfig>(
    `/api/v1/portal/companies/${companyId}/config/escalation`,
    token,
  );
}

export async function updateCompanyConfig(
  token: string,
  companyId: string,
  body: CompanyConfigUpdate,
): Promise<CompanyConfig> {
  return apiFetch<CompanyConfig>(
    `/api/v1/companies/${companyId}/config`,
    token,
    { method: "PUT", body: JSON.stringify(body) },
  );
}

// ── Products ─────────────────────────────────────────────────────────

export type Product = {
  id: string;
  company_id: string;
  name: string;
  sku: string | null;
  category: string | null;
  description: string | null;
  price_json: Record<string, unknown> | null;
  attributes_json: Record<string, unknown> | null;
  synonyms: string[];
  is_active: boolean;
  weaviate_indexed: boolean;
  created_at: string;
  updated_at: string;
};

export type ProductCreate = {
  name: string;
  sku?: string | null;
  category?: string | null;
  description?: string | null;
  price_json?: Record<string, unknown> | null;
  attributes_json?: Record<string, unknown> | null;
  synonyms?: string[];
  is_active?: boolean;
};

export type ProductUpdate = Partial<ProductCreate>;

export type ProductListResult = {
  products: Product[];
  total: number;
};

export type ReindexResult = {
  product_id: string;
  name: string;
  success: boolean;
  message: string;
};

export type BulkReindexResponse = {
  queued: number;
  message: string;
};

export type ProductAnalyticsItem = {
  product_id: string;
  name: string;
  sku: string | null;
  category: string | null;
  retrieved_count: number;
  suggested_count: number;
  unique_conversations: number;
  suggestion_rate_pct: number;
};

export type ProductAnalyticsResponse = {
  period_days: number;
  total_events: number;
  items: ProductAnalyticsItem[];
  top_retrieved: ProductAnalyticsItem[];
  top_suggested: ProductAnalyticsItem[];
  series: Array<{
    date: string;
    retrieved_count: number;
    suggested_count: number;
  }>;
};

export async function listProducts(
  token: string,
  companyId: string,
  opts?: { isActive?: boolean; category?: string; q?: string; limit?: number; offset?: number },
): Promise<ProductListResult> {
  const params = new URLSearchParams();
  if (opts?.isActive !== undefined) params.set("is_active", String(opts.isActive));
  if (opts?.category) params.set("category", opts.category);
  if (opts?.q) params.set("q", opts.q);
  if (opts?.limit !== undefined) params.set("limit", String(opts.limit));
  if (opts?.offset !== undefined) params.set("offset", String(opts.offset));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<ProductListResult>(`/api/v1/companies/${companyId}/products${qs}`, token);
}

export async function getProduct(token: string, companyId: string, productId: string): Promise<Product> {
  return apiFetch<Product>(`/api/v1/companies/${companyId}/products/${productId}`, token);
}

export async function createProduct(token: string, companyId: string, body: ProductCreate): Promise<Product> {
  return apiFetch<Product>(`/api/v1/companies/${companyId}/products`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateProduct(
  token: string,
  companyId: string,
  productId: string,
  body: ProductUpdate,
): Promise<Product> {
  return apiFetch<Product>(`/api/v1/companies/${companyId}/products/${productId}`, token, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteProduct(token: string, companyId: string, productId: string): Promise<void> {
  await apiFetch(`/api/v1/companies/${companyId}/products/${productId}`, token, { method: "DELETE" });
}

export async function reindexProduct(
  token: string,
  companyId: string,
  productId: string,
): Promise<ReindexResult> {
  return apiFetch<ReindexResult>(
    `/api/v1/companies/${companyId}/products/${productId}/reindex`,
    token,
    { method: "POST" },
  );
}

export async function reindexAllProducts(
  token: string,
  companyId: string,
): Promise<BulkReindexResponse> {
  return apiFetch<BulkReindexResponse>(
    `/api/v1/companies/${companyId}/products/reindex-all`,
    token,
    { method: "POST" },
  );
}

export async function getProductAnalytics(
  token: string,
  companyId: string,
  periodDays = 30,
  limit = 20,
): Promise<ProductAnalyticsResponse> {
  return apiFetch<ProductAnalyticsResponse>(
    `/api/v1/companies/${companyId}/analytics/products?period_days=${periodDays}&limit=${limit}`,
    token,
  );
}

export type WeaviateEnsureResult = {
  collection_name: string;
  created: boolean;
  already_existed: boolean;
};

/**
 * Idempotent: create the Weaviate collection for this company if it is
 * missing.  Also sets `onboarding_status.weaviate_ready = true` so the
 * readiness gate is cleared.
 */
export async function weaviateEnsureCollection(
  token: string,
  companyId: string,
): Promise<WeaviateEnsureResult> {
  return apiFetch<WeaviateEnsureResult>(
    `/api/v1/companies/${companyId}/weaviate/ensure-collection`,
    token,
    { method: "POST" },
  );
}

export type CompanyLifecycleStatus =
  | "draft"
  | "active"
  | "inactive"
  | "suspended";

export async function patchCompanyStatus(
  token: string,
  companyId: string,
  status: CompanyLifecycleStatus,
): Promise<unknown> {
  return apiFetch(`/api/v1/companies/${companyId}/status`, token, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// ── Documents ───────────────────────────────────────────────────────

export type DocumentRow = {
  id: string;
  company_id: string;
  file_name: string;
  status: string;
  mime_type: string;
  created_at: string;
};

export type DocumentListResult = {
  documents: DocumentRow[];
  total: number;
};

export async function listDocuments(
  token: string,
  companyId: string,
): Promise<DocumentListResult> {
  return apiFetch<DocumentListResult>(
    `/api/v1/companies/${companyId}/documents`,
    token,
  );
}

async function parseEnvelope<T>(res: Response): Promise<T> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok || !body || typeof body !== "object") {
    const d = body as { detail?: string } | null;
    throw new Error(d?.detail || `HTTP ${res.status}`);
  }
  const b = body as { success?: boolean; data?: T; error?: string };
  if (b.success === false) throw new Error(b.error || "Request failed");
  if (b.success && b.data !== undefined) return b.data as T;
  throw new Error("Unexpected response");
}

export async function uploadDocument(
  token: string,
  companyId: string,
  file: File,
): Promise<unknown> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(
    `${apiBase()}/api/v1/companies/${companyId}/documents/upload`,
    {
      method: "POST",
      headers: authHeadersForFetch(token),
      body: fd,
    },
  );
  return parseEnvelope(res);
}

export async function reindexDocument(
  token: string,
  companyId: string,
  documentId: string,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/companies/${companyId}/documents/${documentId}/index`,
    token,
    { method: "POST" },
  );
}


// ── Handoffs ─────────────────────────────────────────────────────────

export type HandoffRow = {
  id: string;
  company_id: string;
  conversation_id: string;
  status: string;
  reason: string | null;
  assigned_agent_id: string | null;
  requested_by: string;
  created_at: string;
};

export async function listCompanyHandoffs(
  token: string,
  companyId: string,
  status?: string,
): Promise<HandoffRow[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch<HandoffRow[]>(
    `/api/v1/companies/${companyId}/handoffs${q}`,
    token,
  );
}

export async function assignHandoff(
  token: string,
  handoffId: string,
  agentId: string,
): Promise<HandoffRow> {
  return apiFetch<HandoffRow>(`/api/v1/handoffs/${handoffId}/assign`, token, {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export async function resolveHandoff(
  token: string,
  handoffId: string,
  note?: string,
): Promise<HandoffRow> {
  return apiFetch<HandoffRow>(`/api/v1/handoffs/${handoffId}/resolve`, token, {
    method: "POST",
    body: JSON.stringify({ resolution_note: note ?? null }),
  });
}

export async function requestConversationHandoff(
  token: string,
  conversationId: string,
  reason?: string,
): Promise<HandoffRow> {
  return apiFetch<HandoffRow>(
    `/api/v1/conversations/${conversationId}/handoff`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        reason: reason ?? null,
        requested_by: "customer",
      }),
    },
  );
}

export async function resumeConversationBot(
  token: string,
  conversationId: string,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/conversations/${conversationId}/resume-bot`,
    token,
    { method: "POST" },
  );
}

// ── Analytics ────────────────────────────────────────────────────────

export async function analyticsOverview(
  token: string,
  companyId: string,
  periodDays = 30,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/companies/${companyId}/analytics/overview?period_days=${periodDays}`,
    token,
  );
}

export async function analyticsLanguages(
  token: string,
  companyId: string,
  periodDays = 30,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/companies/${companyId}/analytics/languages?period_days=${periodDays}`,
    token,
  );
}

export type LeadWarmthDailyPoint = {
  date: string;
  hot: number;
  warm: number;
  cold: number;
};

export type LeadWarmthAnalytics = {
  company_id: string;
  period_days: number;
  series: LeadWarmthDailyPoint[];
  totals: Record<"hot" | "warm" | "cold", number>;
};

export async function analyticsLeads(
  token: string,
  companyId: string,
  periodDays = 30,
): Promise<LeadWarmthAnalytics> {
  return apiFetch<LeadWarmthAnalytics>(
    `/api/v1/companies/${companyId}/analytics/leads?period_days=${periodDays}`,
    token,
  );
}

export async function analyticsFallbacks(
  token: string,
  companyId: string,
  periodDays = 30,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/companies/${companyId}/analytics/fallbacks?period_days=${periodDays}`,
    token,
  );
}

export async function analyticsHandoffs(
  token: string,
  companyId: string,
  periodDays = 30,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/companies/${companyId}/analytics/handoffs?period_days=${periodDays}`,
    token,
  );
}

export async function analyticsTopQueries(
  token: string,
  companyId: string,
  periodDays = 30,
): Promise<unknown> {
  return apiFetch(
    `/api/v1/companies/${companyId}/analytics/top-queries?period_days=${periodDays}`,
    token,
  );
}

// ── Twilio per-company credentials ──────────────────────────────────

export type TwilioConfigSave = {
  twilio_whatsapp_number: string;
  twilio_account_sid: string;
  twilio_auth_token: string;
  enable_twilio_provider?: boolean;
};

export type TwilioConfigSaveResponse = {
  company_id: string;
  whatsapp_provider: string;
  twilio_whatsapp_number: string | null;
  twilio_account_sid: string | null;
  has_twilio_auth_token: boolean;
  webhook_path: string;
};

export async function saveTwilioConfig(
  token: string,
  companyId: string,
  body: TwilioConfigSave,
): Promise<TwilioConfigSaveResponse> {
  return apiFetch<TwilioConfigSaveResponse>(
    `/api/v1/portal/admin/companies/${companyId}/twilio`,
    token,
    { method: "POST", body: JSON.stringify(body) },
  );
}

// ── AiSensy per-company (admin + X-Admin-Key) ───────────────────────

export type AisensyConfigSave = {
  aisensy_whatsapp_number: string;
  aisensy_project_id: string;
  /** Omit or empty to keep the existing encrypted key. */
  aisensy_api_key?: string | null;
  enable_aisensy_provider?: boolean;
};

export type AisensyConfigSaveResponse = {
  company_id: string;
  whatsapp_provider: string;
  aisensy_whatsapp_number: string | null;
  aisensy_project_id: string | null;
  has_aisensy_api_key: boolean;
};

export async function saveAisensyConfig(
  token: string,
  companyId: string,
  body: AisensyConfigSave,
): Promise<AisensyConfigSaveResponse> {
  return apiFetch<AisensyConfigSaveResponse>(
    `/api/v1/portal/admin/companies/${companyId}/aisensy`,
    token,
    { method: "POST", body: JSON.stringify(body) },
  );
}

// ── Meta WhatsApp Cloud API (admin + X-Admin-Key) ───────────────────

export type MetaWhatsappConfigSave = {
  meta_phone_number_id: string;
  meta_waba_id?: string | null;
  meta_graph_access_token?: string | null;
  meta_app_secret?: string | null;
  meta_webhook_verify_token?: string | null;
  enable_meta_provider?: boolean;
};

export type MetaWhatsappConfigSaveResponse = {
  company_id: string;
  whatsapp_provider: string;
  meta_phone_number_id: string | null;
  meta_waba_id: string | null;
  has_meta_graph_token: boolean;
  has_meta_app_secret: boolean;
  has_meta_webhook_verify_token: boolean;
  webhook_get_post_path: string;
};

export async function saveMetaWhatsappConfig(
  token: string,
  companyId: string,
  body: MetaWhatsappConfigSave,
): Promise<MetaWhatsappConfigSaveResponse> {
  return apiFetch<MetaWhatsappConfigSaveResponse>(
    `/api/v1/portal/admin/companies/${companyId}/meta-whatsapp`,
    token,
    { method: "POST", body: JSON.stringify(body) },
  );
}

// ── Portal users (global admin) ─────────────────────────────────────

export type PortalUser = {
  id: string;
  username: string;
  role: "admin" | "user";
  company_id: string | null;
  is_active: boolean;
};

export async function listPortalUsers(token: string): Promise<PortalUser[]> {
  return apiFetch<PortalUser[]>("/api/v1/portal/admin/users", token);
}

export async function createPortalUser(
  token: string,
  body: {
    username: string;
    password: string;
    role: "admin" | "user";
    company_id?: string | null;
  },
): Promise<PortalUser> {
  return apiFetch<PortalUser>("/api/v1/portal/admin/users", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── WhatsApp inbox (per-company) ────────────────────────────────────

export async function resetPortalUserPassword(
  token: string,
  userId: string,
  password: string,
): Promise<PortalUser> {
  return apiFetch<PortalUser>(
    `/api/v1/portal/admin/users/${userId}/reset-password`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ password }),
    },
  );
}

export type InboxConversation = {
  id: string;
  company_id: string;
  customer_phone: string;
  current_mode: string;
  status: string;
  detected_language: string | null;
  assigned_agent_id: string | null;
  last_message_at: string | null;
  lead_warmth: string | null;
  lead_warmth_locked?: boolean;
  inquiry_complete: boolean;
  inquiry_completed_at: string | null;
  last_message_preview: string | null;
  created_at: string;
  updated_at: string;
};

export type InboxMessage = {
  id: string;
  conversation_id: string;
  company_id: string;
  sender_type: string;
  message_text: string;
  normalized_text: string | null;
  language: string | null;
  response_type: string | null;
  external_message_id: string | null;
  created_at: string;
};

export type SheetPreviewRow = {
  conversation_id: string;
  customer_phone: string;
  conversations_last_10_user_messages: string;
  summary: string;
  lead_type: string;
  last_message_at: string | null;
  inquiry_complete: boolean;
};

export async function listSheetPreviewRows(
  token: string,
  companyId: string,
  params?: { inquiry?: "open" | "complete" },
): Promise<SheetPreviewRow[]> {
  const q = new URLSearchParams();
  if (params?.inquiry) q.set("inquiry", params.inquiry);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return apiFetch<SheetPreviewRow[]>(
    `/api/v1/portal/companies/${companyId}/sheet-preview${suffix}`,
    token,
  );
}

export async function listInboxConversations(
  token: string,
  companyId: string,
  params?: { inquiry?: "open" | "complete" },
): Promise<InboxConversation[]> {
  const q = new URLSearchParams();
  if (params?.inquiry) q.set("inquiry", params.inquiry);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return apiFetch<InboxConversation[]>(
    `/api/v1/portal/companies/${companyId}/inbox/conversations${suffix}`,
    token,
  );
}

export async function getInboxMessages(
  token: string,
  companyId: string,
  conversationId: string,
): Promise<InboxMessage[]> {
  return apiFetch<InboxMessage[]>(
    `/api/v1/portal/companies/${companyId}/inbox/conversations/${conversationId}/messages`,
    token,
  );
}

export async function sendInboxMessage(
  token: string,
  companyId: string,
  conversationId: string,
  messageText: string,
): Promise<InboxMessage> {
  return apiFetch<InboxMessage>(
    `/api/v1/portal/companies/${companyId}/inbox/conversations/${conversationId}/messages`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ message_text: messageText }),
    },
  );
}

export async function patchInboxConversation(
  token: string,
  companyId: string,
  conversationId: string,
  body: { lead_warmth?: string | null; inquiry_complete?: boolean },
): Promise<InboxConversation> {
  return apiFetch<InboxConversation>(
    `/api/v1/portal/companies/${companyId}/inbox/conversations/${conversationId}`,
    token,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

// ── WhatsApp campaigns / follow-ups ────────────────────────────────────────

export type CampaignPreview = {
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  errors: string[];
};

export type WhatsAppCampaign = {
  id: string;
  company_id: string;
  name: string;
  status: string;
  template_name: string;
  language_code: string;
  body_variable_mappings: Array<string | Record<string, unknown>>;
  header_media_url_mapping: string | null;
  total_recipients: number;
  queued_count: number;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  created_at: string;
  updated_at: string;
};

export type FollowupRule = {
  id: string;
  company_id: string;
  name: string;
  is_active: boolean;
  steps_json: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type OutboxJob = {
  id: string;
  kind: string;
  status: string;
  to_number: string;
  template_name: string;
  language_code: string;
  attempts: number;
  next_attempt_at: string;
  last_error: string | null;
  created_at: string;
};

/** Meta Graph API template row (subset used by portal preview). */
export type MetaWhatsAppTemplate = {
  name: string;
  language?: string | Record<string, unknown> | null;
  status?: string | null;
  category?: string | null;
  components?: Array<Record<string, unknown>>;
};

export async function listMetaWhatsAppTemplates(
  token: string,
  companyId: string,
): Promise<MetaWhatsAppTemplate[]> {
  return apiFetch<MetaWhatsAppTemplate[]>(
    `/api/v1/portal/companies/${companyId}/meta-templates`,
    token,
  );
}

/** Submit a new TEXT template to Meta (utility/marketing); Meta must approve before sends outside session. */
export type MetaTemplateCreatePayload = {
  name: string;
  category?: "utility" | "marketing";
  language: string;
  body_text: string;
  footer_text?: string | null;
  header_text?: string | null;
  body_example_values?: string[];
};

export async function createMetaWhatsAppTemplate(
  token: string,
  companyId: string,
  body: MetaTemplateCreatePayload,
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/portal/companies/${companyId}/meta-templates`,
    token,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function previewCampaignUpload(
  token: string,
  companyId: string,
  file: File,
): Promise<CampaignPreview> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<CampaignPreview>(
    `/api/v1/portal/companies/${companyId}/campaigns/preview`,
    token,
    { method: "POST", body: form },
  );
}

export async function listCampaigns(token: string, companyId: string): Promise<WhatsAppCampaign[]> {
  return apiFetch<WhatsAppCampaign[]>(`/api/v1/portal/companies/${companyId}/campaigns`, token);
}

export async function createCampaign(
  token: string,
  companyId: string,
  body: {
    name: string;
    template_name: string;
    language_code: string;
    phone_column: string;
    body_variable_mappings: Array<string | Record<string, unknown>>;
    header_media_url_mapping?: string | null;
    rows: Record<string, unknown>[];
  },
): Promise<WhatsAppCampaign> {
  return apiFetch<WhatsAppCampaign>(`/api/v1/portal/companies/${companyId}/campaigns`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function campaignAction(
  token: string,
  companyId: string,
  campaignId: string,
  action: "start" | "pause" | "cancel" | "retry_failed",
): Promise<WhatsAppCampaign> {
  return apiFetch<WhatsAppCampaign>(
    `/api/v1/portal/companies/${companyId}/campaigns/${campaignId}/action`,
    token,
    { method: "POST", body: JSON.stringify({ action }) },
  );
}

export async function listOutboxJobs(
  token: string,
  companyId: string,
  params?: { campaignId?: string; status?: string },
): Promise<OutboxJob[]> {
  const q = new URLSearchParams();
  if (params?.campaignId) q.set("campaign_id", params.campaignId);
  if (params?.status) q.set("status", params.status);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return apiFetch<OutboxJob[]>(`/api/v1/portal/companies/${companyId}/outbox-jobs${suffix}`, token);
}

export async function listFollowupRules(token: string, companyId: string): Promise<FollowupRule[]> {
  return apiFetch<FollowupRule[]>(`/api/v1/portal/companies/${companyId}/followup-rules`, token);
}

export async function createFollowupRule(
  token: string,
  companyId: string,
  body: { name: string; is_active: boolean; steps: Array<Record<string, unknown>> },
): Promise<FollowupRule> {
  return apiFetch<FollowupRule>(`/api/v1/portal/companies/${companyId}/followup-rules`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateFollowupRule(
  token: string,
  companyId: string,
  ruleId: string,
  body: { name?: string; is_active?: boolean; steps?: Array<Record<string, unknown>> },
): Promise<FollowupRule> {
  return apiFetch<FollowupRule>(`/api/v1/portal/companies/${companyId}/followup-rules/${ruleId}`, token, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteFollowupRule(token: string, companyId: string, ruleId: string): Promise<void> {
  await apiFetch<Record<string, unknown>>(
    `/api/v1/portal/companies/${companyId}/followup-rules/${ruleId}`,
    token,
    { method: "DELETE" },
  );
}

// ── Quick-send (one-shot bulk campaign) ─────────────────────────────────────

export type QuickSendResult = {
  campaign_id: string;
  campaign_status: string;
  template_name: string;
  template_status: string;
  message: string;
};

export type QuickSendRow = Record<string, string>;

export async function quickSendCampaign(
  token: string,
  companyId: string,
  body: {
    campaign_name: string;
    template_name: string;
    template_body: string;
    template_header?: string;
    template_footer?: string;
    language_code: string;
    category: "marketing" | "utility";
    phone_column: string;
    rows: QuickSendRow[];
  },
): Promise<QuickSendResult> {
  return apiFetch<QuickSendResult>(
    `/api/v1/portal/companies/${companyId}/campaigns/quick-send`,
    token,
    { method: "POST", body: JSON.stringify(body) },
  );
}
