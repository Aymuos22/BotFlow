import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import * as XLSX from "xlsx";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getLanguageCatalog,
  listCompanies,
  type CompanySummary,
  type LanguageOption,
} from "../lib/api";
import {
  activateCompany,
  analyticsOverview,
  analyticsFallbacks,
  analyticsHandoffs,
  analyticsLanguages,
  analyticsLeads,
  analyticsTopQueries,
  assignHandoff,
  campaignAction,
  createCampaign,
  createFollowupRule,
  createProduct,
  deleteProduct,
  deleteFollowupRule,
  getCompanyConfig,
  getCompanyConfigOverview,
  getCompanyReadiness,
  getProductAnalytics,
  listCampaigns,
  listCompanyHandoffs,
  listDocuments,
  listFollowupRules,
  listOutboxJobs,
  listProducts,
  patchCompanyStatus,
  previewCampaignUpload,
  reindexAllProducts,
  reindexDocument,
  reindexProduct,
  requestConversationHandoff,
  resolveHandoff,
  resumeConversationBot,
  updateProduct,
  type BulkReindexResponse,
  type CompanyConfig,
  type CompanyLifecycleStatus,
  type PortalConfigOverview,
  type Product,
  type ProductAnalyticsResponse,
  type ProductCreate,
  type CampaignPreview,
  type FollowupRule,
  type OutboxJob,
  type WhatsAppCampaign,
  updateFollowupRule,
  updateCompanyConfig,
  saveAisensyConfig,
  saveMetaWhatsappConfig,
  saveTwilioConfig,
  uploadDocument,
  weaviateEnsureCollection,
  type WeaviateEnsureResult,
  type HandoffRow,
  type LeadWarmthAnalytics,
  type WhatsAppProvider,
} from "../lib/supportApi";
import FollowupTemplatePicker, {
  parseFollowupBodyVariablesCsv,
} from "../components/FollowupTemplatePicker";
import { PageLoader, Spinner } from "../components/Spinner";
import { useToast } from "../context/ToastContext";
import CompanyInbox from "./CompanyInbox";

/** If overview + meta catalog both fail (offline), still allow saving known codes. */
const FALLBACK_LANGUAGE_CATALOG: LanguageOption[] = [
  {
    code: "english",
    label: "English",
    description: "Formal or casual replies in English.",
  },
  {
    code: "hindi",
    label: "Hindi (Devanagari)",
    description: "Replies in Hindi using देवनागरी script.",
  },
  {
    code: "hinglish",
    label: "Hinglish (Roman Hindi)",
    description: "Roman-script Hindi mixed with English (typical WhatsApp style).",
  },
];

type SupportTab = "overview" | "config" | "documents" | "products" | "campaigns" | "followups" | "whatsapp" | "inbox" | "handoffs" | "analytics";

const TABS: { id: SupportTab; label: string }[] = [
  { id: "overview",   label: "Overview" },
  { id: "config",     label: "Config" },
  { id: "documents",  label: "Documents" },
  { id: "products",   label: "Products" },
  { id: "campaigns",  label: "Campaigns" },
  { id: "followups",  label: "Follow-ups" },
  { id: "whatsapp",   label: "WhatsApp" },
  { id: "inbox",      label: "Inbox" },
  { id: "handoffs",   label: "Handoffs" },
  { id: "analytics",  label: "Analytics" },
];

/** Public API base for webhook URLs (must match where the API is reachable). */
const PUBLIC_API_WEBHOOK_BASE = "https://44.212.38.114.nip.io";
const TWILIO_INBOUND_WEBHOOK_URL = `${PUBLIC_API_WEBHOOK_BASE}/api/v1/webhooks/twilio/messages`;
const AISENSY_INBOUND_WEBHOOK_URL = `${PUBLIC_API_WEBHOOK_BASE}/api/v1/webhooks/aisensy/messages`;
const META_WHATSAPP_WEBHOOK_URL = `${PUBLIC_API_WEBHOOK_BASE}/api/v1/webhooks/meta/whatsapp`;

type Props = { accessToken: string };

function jsonPretty(v: unknown): string {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
}

function parseSynonymsText(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  text
    .split(/[,\n]/)
    .map((s) => s.trim().replace(/\s+/g, " "))
    .filter(Boolean)
    .forEach((s) => {
      const key = s.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push(s);
    });
  return out;
}

function synonymsText(values: string[] | null | undefined): string {
  return (values ?? []).join("\n");
}

function attrString(attrs: unknown, ...keys: string[]): string {
  if (!attrs || typeof attrs !== "object" || Array.isArray(attrs)) return "";
  const data = attrs as Record<string, unknown>;
  const lowered = new Map(Object.entries(data).map(([k, v]) => [k.toLowerCase(), v]));
  for (const key of keys) {
    const value = data[key] ?? lowered.get(key.toLowerCase());
    if (typeof value === "string") return value.trim();
    if (value !== null && value !== undefined) return String(value).trim();
  }
  return "";
}

function getProductImageUrl(product: Pick<Product, "attributes_json">): string {
  return attrString(product.attributes_json, "image_url", "imageUrl", "image", "image_link", "photo_url", "picture_url");
}

function getProductImageAlt(product: Pick<Product, "attributes_json" | "name">): string {
  return attrString(product.attributes_json, "image_alt", "imageAlt", "alt_text", "alt") || product.name;
}

function mergeProductImageAttrs(
  attrs: Record<string, unknown> | null,
  imageUrl: string,
  imageAlt: string,
  productName: string,
): Record<string, unknown> | null {
  const next: Record<string, unknown> = { ...(attrs ?? {}) };
  const cleanUrl = imageUrl.trim();
  const cleanAlt = imageAlt.trim();
  delete next.image_url;
  delete next.image_alt;
  if (cleanUrl) {
    next.image_url = cleanUrl;
    next.image_alt = cleanAlt || productName.trim();
  }
  return Object.keys(next).length ? next : null;
}

/** Keys that should not appear in portal JSON views (legacy infra). */
const INTERNAL_SESSION_KEY_RE = /^waha_/i;

function omitInternalSessionKeysDeep(v: unknown): unknown {
  if (v === null || typeof v !== "object") return v;
  if (Array.isArray(v)) return v.map(omitInternalSessionKeysDeep);
  const o = v as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const [k, val] of Object.entries(o)) {
    if (INTERNAL_SESSION_KEY_RE.test(k)) continue;
    if (k === "whatsapp_provider" && typeof val === "string" && val.toLowerCase() === "waha") {
      continue;
    }
    out[k] = omitInternalSessionKeysDeep(val);
  }
  return out;
}

function jsonPrettyUi(v: unknown): string {
  return jsonPretty(omitInternalSessionKeysDeep(v));
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

type FlatCell = string | number | boolean | null;

function scalarCell(v: unknown): FlatCell {
  if (v === null || v === undefined) return null;
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    return v;
  }
  return String(v);
}

function flattenObject(
  input: Record<string, unknown>,
  prefix = "",
): Record<string, unknown> {
  const out: Record<string, FlatCell> = {};

  function walk(value: unknown, path: string): void {
    if (isPlainObject(value)) {
      for (const [k, v] of Object.entries(value)) {
        const next = path ? `${path}.${k}` : k;
        walk(v, next);
      }
      return;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        out[path] = null;
        return;
      }

      const allPrimitive = value.every(
        (x) =>
          x === null ||
          x === undefined ||
          typeof x === "string" ||
          typeof x === "number" ||
          typeof x === "boolean",
      );
      if (allPrimitive) {
        out[path] = value.map((x) => String(scalarCell(x) ?? "")).join(" | ");
        return;
      }

      value.forEach((item, idx) => {
        const indexed = `${path}[${idx + 1}]`;
        walk(item, indexed);
      });
      return;
    }

    out[path] = scalarCell(value);
  }

  walk(input, prefix);
  return out;
}

function setBestEffortColumnWidths(
  ws: XLSX.WorkSheet,
  headers: string[],
  rows: Array<Record<string, FlatCell>>,
) {
  const widths = headers.map((h) => {
    let max = h.length;
    for (const r of rows) {
      const text = String(r[h] ?? "");
      if (text.length > max) max = text.length;
    }
    return { wch: Math.min(Math.max(max + 2, 12), 60) };
  });
  ws["!cols"] = widths;
}

function downloadXlsx(filename: string, sheets: Record<string, unknown>) {
  const wb = XLSX.utils.book_new();
  for (const [name, data] of Object.entries(sheets)) {
    const clean = omitInternalSessionKeysDeep(data);
    let ws: XLSX.WorkSheet;

    if (Array.isArray(clean)) {
      const rows = clean.map((item) =>
        isPlainObject(item)
          ? flattenObject(item)
          : { value: scalarCell(item) },
      );
      const headers = Array.from(
        rows.reduce((acc, row) => {
          Object.keys(row).forEach((k) => acc.add(k));
          return acc;
        }, new Set<string>()),
      );
      ws = XLSX.utils.json_to_sheet(rows, { header: headers });
      setBestEffortColumnWidths(ws, headers, rows);
    } else if (isPlainObject(clean)) {
      const row = flattenObject(clean);
      const headers = Object.keys(row);
      ws = XLSX.utils.json_to_sheet([row], { header: headers });
      setBestEffortColumnWidths(ws, headers, [row]);
    } else {
      ws = XLSX.utils.json_to_sheet(
        [{ value: scalarCell(clean) }],
        { header: ["value"] },
      );
      ws["!cols"] = [{ wch: 50 }];
    }

    XLSX.utils.book_append_sheet(wb, ws, name.slice(0, 31) || "sheet");
  }
  const bytes = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  const blob = new Blob([bytes], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function n(v: unknown, fallback = 0): number {
  const x = typeof v === "number" ? v : Number(v);
  return Number.isFinite(x) ? x : fallback;
}

function splitColumnsText(text: string): string[] {
  return text.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
}

const PIE_COLORS = ["#1d4ed8", "#64748b", "#7c3aed", "#d97706", "#dc2626", "#059669"];

const SAMPLE_CAMPAIGN_ROWS = [
  {
    phone: "919876543210",
  },
  {
    phone: "918765432109",
  },
];

export default function CompanySupport({ accessToken }: Props) {
  const { companyId = "" } = useParams<{ companyId: string }>();
  const [tab, setTab] = useState<SupportTab>("overview");

  const [meta, setMeta] = useState<CompanySummary | null>(null);
  const [readiness, setReadiness] = useState<unknown>(null);
  const [config, setConfig] = useState<CompanyConfig | null>(null);
  /** Read-only snapshot from GET /portal/companies/.../config/overview */
  const [portalOverview, setPortalOverview] = useState<PortalConfigOverview | null>(null);
  const [systemPrompt, setSystemPrompt] = useState("");
  // ── RAG config form ────────────────────────────────────────────────
  const [ragTopK, setRagTopK] = useState<number | "">("");
  const [ragScoreThreshold, setRagScoreThreshold] = useState<number | "">("");
  const [ragHybridAlpha, setRagHybridAlpha] = useState<number | "">("");
  const [ragStrategy, setRagStrategy] = useState("top");
  // ── Fallback config form ───────────────────────────────────────────
  const [fallbackEnglish, setFallbackEnglish] = useState("");
  const [fallbackHindi, setFallbackHindi] = useState("");
  const [fallbackHinglish, setFallbackHinglish] = useState("");
  // ── Handoff config form ────────────────────────────────────────────
  const [handoffKeywordsStr, setHandoffKeywordsStr] = useState("");
  const [handoffOnLowConf, setHandoffOnLowConf] = useState(false);
  const [handoffLowConfThreshold, setHandoffLowConfThreshold] = useState<number | "">("");
  const [handoffAckEnglish, setHandoffAckEnglish] = useState("");
  const [handoffAckHindi, setHandoffAckHindi] = useState("");
  const [handoffAckHinglish, setHandoffAckHinglish] = useState("");
  /** Staff/supervisor WhatsApp for new-handoff alerts; API normalizes to whatsapp:+E164. */
  const [handoffStaffNotifyWhatsapp, setHandoffStaffNotifyWhatsapp] = useState("");
  // ── Business hours form ────────────────────────────────────────────
  const [bhTimezone, setBhTimezone] = useState("Asia/Kolkata");
  const [bhSchedule, setBhSchedule] = useState<Record<string, { open: string; close: string; enabled: boolean }>>({
    monday:    { open: "09:00", close: "18:00", enabled: true },
    tuesday:   { open: "09:00", close: "18:00", enabled: true },
    wednesday: { open: "09:00", close: "18:00", enabled: true },
    thursday:  { open: "09:00", close: "18:00", enabled: true },
    friday:    { open: "09:00", close: "18:00", enabled: true },
    saturday:  { open: "10:00", close: "14:00", enabled: false },
    sunday:    { open: "10:00", close: "14:00", enabled: false },
  });
  const [bhOutOfHoursMsg, setBhOutOfHoursMsg] = useState("");
  // ── Twilio credentials form ────────────────────────────────────────
  const [twilioAccountSid, setTwilioAccountSid] = useState("");
  const [twilioAuthToken, setTwilioAuthToken] = useState("");
  const [twilioHasSavedToken, setTwilioHasSavedToken] = useState(false);
  const [twilioCredBusy, setTwilioCredBusy] = useState(false);
  const [twilioCredOk, setTwilioCredOk] = useState<string | null>(null);
  const [twilioCredErr, setTwilioCredErr] = useState<string | null>(null);

  const [langs, setLangs] = useState<string[]>(["english"]);
  const [defaultLang, setDefaultLang] = useState("english");
  const [langCatalog, setLangCatalog] = useState<LanguageOption[]>(FALLBACK_LANGUAGE_CATALOG);
  const [agentInactivityMinutes, setAgentInactivityMinutes] = useState<number | "">("");
  const [configActive, setConfigActive] = useState(true);
  const [googleSheetsEnabled, setGoogleSheetsEnabled] = useState(true);
  const [googleSheetId, setGoogleSheetId] = useState("");
  const [lifecycle, setLifecycle] = useState<CompanyLifecycleStatus>("active");
  const [twilioWhatsAppNumber, setTwilioWhatsAppNumber] = useState("");
  const [whatsAppProvider, setWhatsAppProvider] = useState<WhatsAppProvider>("twilio");
  const [aisensyWhatsappNumber, setAisensyWhatsappNumber] = useState("");
  const [aisensyProjectId, setAisensyProjectId] = useState("");
  const [aisensyApiKey, setAisensyApiKey] = useState("");
  const [aisensyBusy, setAisensyBusy] = useState(false);
  const [aisensyErr, setAisensyErr] = useState<string | null>(null);
  const [aisensyOk, setAisensyOk] = useState<string | null>(null);
  const [metaPhoneNumberId, setMetaPhoneNumberId] = useState("");
  const [metaWabaId, setMetaWabaId] = useState("");
  const [metaGraphToken, setMetaGraphToken] = useState("");
  const [metaAppSecret, setMetaAppSecret] = useState("");
  const [metaWebhookVerifyToken, setMetaWebhookVerifyToken] = useState("");
  const [metaBusy, setMetaBusy] = useState(false);
  const [metaErr, setMetaErr] = useState<string | null>(null);
  const [metaOk, setMetaOk] = useState<string | null>(null);
  const [docs, setDocs] = useState<{ documents: { id: string; file_name: string; status: string }[]; total: number } | null>(null);
  const [handoffs, setHandoffs] = useState<HandoffRow[]>([]);
  const [weaviateResult, setWeaviateResult] = useState<WeaviateEnsureResult | null>(null);
  // Products state
  const [products, setProducts] = useState<Product[]>([]);
  const [productTotal, setProductTotal] = useState(0);
  const [productAnalytics, setProductAnalytics] = useState<ProductAnalyticsResponse | null>(null);
  const [productForm, setProductForm] = useState<ProductCreate & { id?: string }>({ name: "", is_active: true });
  const [productFormOpen, setProductFormOpen] = useState(false);
  const [productPriceStr, setProductPriceStr] = useState("{}");
  const [productAttrsStr, setProductAttrsStr] = useState("{}");
  const [productSynonymsStr, setProductSynonymsStr] = useState("");
  const [productImageUrl, setProductImageUrl] = useState("");
  const [productImageAlt, setProductImageAlt] = useState("");
  const [campaigns, setCampaigns] = useState<WhatsAppCampaign[]>([]);
  const [campaignPreview, setCampaignPreview] = useState<CampaignPreview | null>(null);
  const [campaignFile, setCampaignFile] = useState<File | null>(null);
  const [campaignName, setCampaignName] = useState("");
  const [campaignTemplate, setCampaignTemplate] = useState("");
  const [campaignLang, setCampaignLang] = useState("en");
  const [campaignPhoneCol, setCampaignPhoneCol] = useState("");
  const [campaignVars, setCampaignVars] = useState("");
  const [campaignMessage, setCampaignMessage] = useState("");
  const [campaignHeaderMediaCol, setCampaignHeaderMediaCol] = useState("");
  const [outboxJobs, setOutboxJobs] = useState<OutboxJob[]>([]);
  const [followupRules, setFollowupRules] = useState<FollowupRule[]>([]);
  const [followupName, setFollowupName] = useState("");
  const [followupTemplate, setFollowupTemplate] = useState("");
  const [followupLang, setFollowupLang] = useState("en");
  const [followupBodyVarsCsv, setFollowupBodyVarsCsv] = useState("");
  const [followupDelay, setFollowupDelay] = useState(1440);
  const [periodDays, setPeriodDays] = useState(30);
  const [overview, setOverview] = useState<unknown>(null);
  const [analyticsLang, setAnalyticsLang] = useState<unknown>(null);
  const [analyticsLeadsData, setAnalyticsLeadsData] = useState<LeadWarmthAnalytics | null>(null);
  const [analyticsFb, setAnalyticsFb] = useState<unknown>(null);
  const [analyticsHo, setAnalyticsHo] = useState<unknown>(null);
  const [analyticsTQ, setAnalyticsTQ] = useState<unknown>(null);
  const [assignByHandoff, setAssignByHandoff] = useState<Record<string, string>>({});
  const [convIdHandoff, setConvIdHandoff] = useState("");
  const [convIdResume, setConvIdResume] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  /** First fetch for this company (full-page loader). */
  const [initialLoading, setInitialLoading] = useState(() => !!companyId);
  /** Analytics panel refresh (inline loaders). */
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setErr(null);
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Request failed";
      setErr(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const loadAnalytics = useCallback(async (opts?: { notifySuccess?: boolean }) => {
    if (!companyId) return;
    setAnalyticsLoading(true);
    try {
      const [o, l, leads, f, ho, tq, pa] = await Promise.all([
        analyticsOverview(accessToken, companyId, periodDays),
        analyticsLanguages(accessToken, companyId, periodDays),
        analyticsLeads(accessToken, companyId, periodDays).catch(() => null),
        analyticsFallbacks(accessToken, companyId, periodDays),
        analyticsHandoffs(accessToken, companyId, periodDays),
        analyticsTopQueries(accessToken, companyId, periodDays),
        getProductAnalytics(accessToken, companyId, periodDays).catch(() => null),
      ]);
      setOverview(o);
      setAnalyticsLang(l);
      setAnalyticsLeadsData(leads as LeadWarmthAnalytics | null);
      setAnalyticsFb(f);
      setAnalyticsHo(ho);
      setAnalyticsTQ(tq);
      setProductAnalytics(pa as ProductAnalyticsResponse | null);
      if (opts?.notifySuccess) toast.success("Analytics updated.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Analytics failed";
      setErr(msg);
      toast.error(msg);
    } finally {
      setAnalyticsLoading(false);
    }
  }, [accessToken, companyId, periodDays, toast]);

  useEffect(() => {
    if (langs.length > 0 && !langs.includes(defaultLang)) {
      setDefaultLang(langs[0]!);
    }
  }, [langs, defaultLang]);

  const loadAll = useCallback(async (opts?: { notifySuccess?: boolean }) => {
    if (!companyId) return;
    setErr(null);
    try {
      // listCompanies is admin-only – non-fatal so non-admin users can still
      // view and edit their company's config.
      const metaCompany = await listCompanies(accessToken)
        .then((list) => list.find((c) => c.id === companyId) ?? null)
        .catch(() => null);
      setMeta(metaCompany);
      setLifecycle((metaCompany?.status as CompanyLifecycleStatus) ?? "active");

      const [r, c, d, h, ov] = await Promise.all([
        getCompanyReadiness(accessToken, companyId).catch(() => null),
        getCompanyConfig(accessToken, companyId),
        listDocuments(accessToken, companyId).catch(() => ({ documents: [], total: 0 })),
        listCompanyHandoffs(accessToken, companyId).catch(() => []),
        getCompanyConfigOverview(accessToken, companyId).catch(() => null),
      ]);
      setReadiness(r);
      setConfig(c);
      setPortalOverview(ov);
      setSystemPrompt(c.system_prompt ?? "");

      // ── Hydrate RAG form ─────────────────────────────────────────
      const rag = (c.rag_config_json ?? {}) as Record<string, unknown>;
      setRagTopK(typeof rag.top_k === "number" ? rag.top_k : "");
      setRagScoreThreshold(typeof rag.score_threshold === "number" ? rag.score_threshold : "");
      setRagHybridAlpha(typeof rag.hybrid_alpha === "number" ? rag.hybrid_alpha : "");
      setRagStrategy(typeof rag.confidence_strategy === "string" ? rag.confidence_strategy : "top");

      // ── Hydrate fallback form ────────────────────────────────────
      const fb = (c.fallback_config_json ?? {}) as Record<string, unknown>;
      setFallbackEnglish(typeof fb.english === "string" ? fb.english : "");
      setFallbackHindi(typeof fb.hindi === "string" ? fb.hindi : "");
      setFallbackHinglish(typeof fb.hinglish === "string" ? fb.hinglish : "");

      // ── Hydrate handoff form ─────────────────────────────────────
      const ho = (c.handoff_config_json ?? {}) as Record<string, unknown>;
      setHandoffKeywordsStr(
        Array.isArray(ho.human_request_keywords)
          ? (ho.human_request_keywords as string[]).join(", ")
          : "",
      );
      setHandoffOnLowConf(Boolean(ho.handoff_on_low_confidence));
      setHandoffLowConfThreshold(
        typeof ho.low_confidence_handoff_threshold === "number"
          ? ho.low_confidence_handoff_threshold
          : "",
      );
      const hoAck = (typeof ho.handoff_acknowledgement === "object" && ho.handoff_acknowledgement !== null
        ? ho.handoff_acknowledgement
        : {}) as Record<string, unknown>;
      setHandoffAckEnglish(typeof hoAck.english === "string" ? hoAck.english : "");
      setHandoffAckHindi(typeof hoAck.hindi === "string" ? hoAck.hindi : "");
      setHandoffAckHinglish(typeof hoAck.hinglish === "string" ? hoAck.hinglish : "");
      setHandoffStaffNotifyWhatsapp(
        typeof c.handoff_staff_notify_whatsapp === "string"
          ? c.handoff_staff_notify_whatsapp
          : "",
      );

      // ── Hydrate business hours form ──────────────────────────────
      const bh = (c.business_hours_json ?? {}) as Record<string, unknown>;
      setBhTimezone(typeof bh.timezone === "string" ? bh.timezone : "Asia/Kolkata");
      setBhOutOfHoursMsg(typeof bh.out_of_hours_message === "string" ? bh.out_of_hours_message : "");
      const _defaultSched: Record<string, { open: string; close: string; enabled: boolean }> = {
        monday:    { open: "09:00", close: "18:00", enabled: true },
        tuesday:   { open: "09:00", close: "18:00", enabled: true },
        wednesday: { open: "09:00", close: "18:00", enabled: true },
        thursday:  { open: "09:00", close: "18:00", enabled: true },
        friday:    { open: "09:00", close: "18:00", enabled: true },
        saturday:  { open: "10:00", close: "14:00", enabled: false },
        sunday:    { open: "10:00", close: "14:00", enabled: false },
      };
      const loadedSched = { ..._defaultSched };
      for (const day of Object.keys(_defaultSched)) {
        const d = bh[day] as Record<string, unknown> | undefined;
        if (d && typeof d === "object") {
          loadedSched[day] = {
            open:    typeof d.open    === "string"  ? d.open    : _defaultSched[day]!.open,
            close:   typeof d.close   === "string"  ? d.close   : _defaultSched[day]!.close,
            enabled: typeof d.enabled === "boolean" ? d.enabled : _defaultSched[day]!.enabled,
          };
        }
      }
      setBhSchedule(loadedSched);

      // ── Hydrate Twilio / AiSensy / provider (numbers from GET /portal/.../config) ─
      setTwilioAccountSid(c.twilio_account_sid ?? "");
      setTwilioAuthToken("");
      setAgentInactivityMinutes(
        typeof c.whatsapp_agent_inactivity_minutes === "number"
          ? c.whatsapp_agent_inactivity_minutes
          : ""
      );
      setTwilioWhatsAppNumber(c.twilio_whatsapp_number ?? "");
      setWhatsAppProvider(((c.whatsapp_provider || "twilio") as WhatsAppProvider));
      setAisensyWhatsappNumber(c.aisensy_whatsapp_number ?? "");
      setAisensyProjectId(c.aisensy_project_id ?? "");
      setAisensyApiKey("");
      setMetaPhoneNumberId(c.meta_phone_number_id ?? "");
      setMetaWabaId(c.meta_waba_id ?? "");
      setMetaGraphToken("");
      setMetaAppSecret("");
      setMetaWebhookVerifyToken("");
      setTwilioHasSavedToken(
        Boolean(c.has_twilio_auth_token) || Boolean(ov?.integration?.has_twilio_auth_token),
      );
      setConfigActive(c.is_active ?? true);
      setGoogleSheetsEnabled(c.google_sheets_enabled ?? true);
      setGoogleSheetId(c.google_sheet_id ?? "");
      setLangs([...(c.supported_languages ?? ["english"])]);
      setDefaultLang(c.default_language ?? "english");
      const cat =
        ov?.language_catalog && ov.language_catalog.length > 0
          ? ov.language_catalog
          : await getLanguageCatalog().catch(() => []);
      setLangCatalog(cat.length > 0 ? cat : FALLBACK_LANGUAGE_CATALOG);
      setDocs(d);
      setHandoffs(Array.isArray(h) ? h : []);
      // Load products
      const pl = await listProducts(accessToken, companyId).catch(() => ({ products: [], total: 0 }));
      setProducts(pl.products);
      setProductTotal(pl.total);
      const [campaignRows, ruleRows, jobRows] = await Promise.all([
        listCampaigns(accessToken, companyId).catch(() => []),
        listFollowupRules(accessToken, companyId).catch(() => []),
        listOutboxJobs(accessToken, companyId).catch(() => []),
      ]);
      setCampaigns(campaignRows);
      setFollowupRules(ruleRows);
      setOutboxJobs(jobRows);
      await loadAnalytics();
      if (opts?.notifySuccess) toast.success("Company data refreshed.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load company config";
      setErr(msg);
      toast.error(msg);
    } finally {
      setInitialLoading(false);
    }
  }, [accessToken, companyId, loadAnalytics, toast]);

  useEffect(() => {
    if (companyId) setInitialLoading(true);
  }, [companyId]);

  useEffect(() => { void loadAll(); }, [loadAll]);

  async function saveConfig(e: FormEvent) {
    e.preventDefault();
    if (langs.length === 0) {
      const msg = "Select at least one supported language.";
      setErr(msg);
      toast.error(msg);
      return;
    }
    if (!langs.includes(defaultLang)) {
      const msg = "Default language must be one of the supported languages.";
      setErr(msg);
      toast.error(msg);
      return;
    }
    // Build RAG config from form fields
    const rag: Record<string, unknown> | null = (() => {
      const r: Record<string, unknown> = {};
      if (ragTopK !== "") r.top_k = Number(ragTopK);
      if (ragScoreThreshold !== "") r.score_threshold = Number(ragScoreThreshold);
      if (ragHybridAlpha !== "") r.hybrid_alpha = Number(ragHybridAlpha);
      if (ragStrategy && ragStrategy !== "top") r.confidence_strategy = ragStrategy;
      return Object.keys(r).length > 0 ? r : null;
    })();
    // Build fallback config from form fields
    const fb: Record<string, unknown> | null = (() => {
      const f: Record<string, unknown> = {};
      if (fallbackEnglish.trim()) f.english = fallbackEnglish.trim();
      if (fallbackHindi.trim()) f.hindi = fallbackHindi.trim();
      if (fallbackHinglish.trim()) f.hinglish = fallbackHinglish.trim();
      return Object.keys(f).length > 0 ? f : null;
    })();
    // Build handoff config from form fields
    const ho: Record<string, unknown> | null = (() => {
      const h: Record<string, unknown> = {};
      const kws = handoffKeywordsStr.split(",").map((s) => s.trim()).filter(Boolean);
      if (kws.length > 0) h.human_request_keywords = kws;
      if (handoffOnLowConf) h.handoff_on_low_confidence = true;
      if (handoffLowConfThreshold !== "") h.low_confidence_handoff_threshold = Number(handoffLowConfThreshold);
      const ack: Record<string, string> = {};
      if (handoffAckEnglish.trim()) ack.english = handoffAckEnglish.trim();
      if (handoffAckHindi.trim()) ack.hindi = handoffAckHindi.trim();
      if (handoffAckHinglish.trim()) ack.hinglish = handoffAckHinglish.trim();
      if (Object.keys(ack).length > 0) h.handoff_acknowledgement = ack;
      return Object.keys(h).length > 0 ? h : null;
    })();
    // Build business hours from form fields
    const bh: Record<string, unknown> | null = (() => {
      const b: Record<string, unknown> = {};
      if (bhTimezone.trim()) b.timezone = bhTimezone.trim();
      if (bhOutOfHoursMsg.trim()) b.out_of_hours_message = bhOutOfHoursMsg.trim();
      for (const [day, val] of Object.entries(bhSchedule)) b[day] = val;
      return Object.keys(b).length > 1 ? b : null;
    })();
    await run(async () => {
      const updated = await updateCompanyConfig(accessToken, companyId, {
        system_prompt: systemPrompt || null,
        default_language: defaultLang,
        supported_languages: langs,
        rag_config_json: rag,
        fallback_config_json: fb,
        handoff_config_json: ho,
        business_hours_json: bh,
        whatsapp_agent_inactivity_minutes:
          agentInactivityMinutes === "" ? null : Number(agentInactivityMinutes),
        whatsapp_provider: whatsAppProvider,
        twilio_whatsapp_number: twilioWhatsAppNumber.trim() ? twilioWhatsAppNumber.trim() : null,
        handoff_staff_notify_whatsapp: handoffStaffNotifyWhatsapp.trim()
          ? handoffStaffNotifyWhatsapp.trim()
          : null,
        google_sheets_enabled: googleSheetsEnabled,
        google_sheet_id: googleSheetId.trim() ? googleSheetId.trim() : null,
        is_active: configActive,
      });
      setConfig(updated);
      try {
        setPortalOverview(await getCompanyConfigOverview(accessToken, companyId));
      } catch {
        /* overview is optional */
      }
      toast.success("Configuration saved.");
    });
  }

  const integrationView = useMemo(() => {
    if (portalOverview?.integration) return portalOverview.integration;
    if (!config) return null;
    return {
      weaviate_collection: config.weaviate_collection,
      is_active: config.is_active ?? true,
      whatsapp_provider: config.whatsapp_provider ?? null,
      twilio_whatsapp_number: config.twilio_whatsapp_number ?? null,
      twilio_account_sid: config.twilio_account_sid ?? null,
      has_twilio_auth_token: Boolean(config.has_twilio_auth_token),
      twilio_credentials_complete: Boolean(
        config.twilio_whatsapp_number &&
          config.twilio_account_sid &&
          config.has_twilio_auth_token,
      ),
      aisensy_whatsapp_number: config.aisensy_whatsapp_number ?? null,
      aisensy_project_id: config.aisensy_project_id ?? null,
      has_aisensy_api_key: Boolean(config.has_aisensy_api_key),
      aisensy_credentials_complete: Boolean(
        config.aisensy_whatsapp_number &&
          config.aisensy_project_id &&
          config.has_aisensy_api_key,
      ),
      handoff_staff_notify_configured: Boolean(config.handoff_staff_notify_whatsapp),
      twilio_credentials_save_path: `/api/v1/portal/admin/companies/${companyId}/twilio`,
      aisensy_credentials_save_path: `/api/v1/portal/admin/companies/${companyId}/aisensy`,
      meta_phone_number_id: config.meta_phone_number_id ?? null,
      has_meta_graph_token: Boolean(config.has_meta_graph_token),
      meta_credentials_complete: Boolean(
        config.meta_phone_number_id &&
          config.has_meta_graph_token &&
          config.has_meta_webhook_verify_token,
      ),
      meta_credentials_save_path: `/api/v1/portal/admin/companies/${companyId}/meta-whatsapp`,
      whatsapp_channel_key: null as string | null,
    };
  }, [portalOverview, config, companyId]);

  if (!companyId) {
    return (
      <div className="card">
        <p className="error">Missing company id.</p>
        <Link to="/admin">← Back</Link>
      </div>
    );
  }

  if (initialLoading) {
    return (
      <div className="dashboard-shell dashboard-shell--loading">
        <PageLoader message="Loading company…" />
      </div>
    );
  }

  const r = readiness as { is_ready_to_activate?: boolean; blocking_reasons?: string[] } | null;
  const ready = r?.is_ready_to_activate === true;
  const blocking = r?.blocking_reasons ?? [];
  const companyName = meta?.display_name ?? meta?.name ?? companyId;

  return (
    <div className="stack dashboard-shell">
      {/* ── Page header ── */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <Link to="/admin" style={{ fontSize: "0.85rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", marginBottom: "0.5rem" }}>
            ← All companies
          </Link>
          <h1 className="page-title">{companyName}</h1>
          <p className="page-header-meta">
            <code style={{ fontSize: "0.8rem" }}>{companyId}</code>
            {meta && (
              <span className={`badge badge--${meta.status.toLowerCase() === "active" ? "active" : meta.status.toLowerCase() === "draft" ? "draft" : "inactive"}`}>
                {meta.status}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void loadAll({ notifySuccess: true })}
          >
            Refresh
          </button>
        </div>
      </div>

      {err && <p className="error">{err}</p>}

      {/* ── Sections ── */}
      <div className="support-workspace">
        <aside className="support-section-nav" aria-label="Company sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`support-section-nav__item${tab === t.id ? " support-section-nav__item--active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </aside>
        <div className="support-panel">

        {/* ── Overview ── */}
        {tab === "overview" && (
          <div className="tab-panel">
            <section>
              <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.05rem", fontWeight: 700 }}>Readiness</h2>
              <pre className="support-pre">{jsonPrettyUi(readiness)}</pre>
              {blocking.length > 0 && (
                <ul style={{ margin: "0.75rem 0 0", paddingLeft: "1.25rem", color: "var(--danger)", fontSize: "0.9rem" }}>
                  {blocking.map((b) => <li key={b}>{b}</li>)}
                </ul>
              )}
              <div style={{ marginTop: "1rem" }}>
                <button
                  type="button"
                  className="primary"
                  disabled={busy || !ready}
                  title={ready ? "" : "Readiness gates not satisfied"}
                  onClick={() => void run(async () => {
                    await activateCompany(accessToken, companyId);
                    toast.success("Activate requested.");
                    await loadAll();
                  })}
                >
                  Activate company
                </button>
              </div>
            </section>

            {portalOverview && (
              <section>
                <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.05rem", fontWeight: 700 }}>Configuration snapshot</h2>
                <p className="lead" style={{ margin: "0 0 0.75rem", fontSize: "0.88rem" }}>
                  RAG defaults (env): <code>top_k={portalOverview.rag.global_defaults.top_k}</code>
                  {" · "}
                  <code>score_threshold={portalOverview.rag.global_defaults.score_threshold}</code>
                  {" · "}
                  embeddings{" "}
                  <strong>{portalOverview.rag.global_defaults.rag_embeddings_enabled ? "on" : "off"}</strong>
                </p>
                <p className="lead" style={{ margin: "0 0 0.75rem", fontSize: "0.88rem" }}>
                  Weaviate <code>{portalOverview.integration.weaviate_collection}</code>
                  {" · "}
                  languages: {portalOverview.prompt.supported_languages.join(", ")}
                </p>
                <button type="button" className="secondary" onClick={() => setTab("config")}>
                  View full config &amp; edit
                </button>
              </section>
            )}

            <section>
              <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.05rem", fontWeight: 700 }}>Lifecycle status</h2>
              <div className="support-row" style={{ gap: "0.75rem" }}>
                <select
                  value={lifecycle}
                  style={{ width: "auto" }}
                  onChange={(e) => setLifecycle(e.target.value as CompanyLifecycleStatus)}
                >
                  {(["draft", "active", "inactive", "suspended"] as const).map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void run(async () => {
                    await patchCompanyStatus(accessToken, companyId, lifecycle);
                    toast.success("Status updated.");
                    await loadAll();
                  })}
                >
                  Save status
                </button>
              </div>
            </section>
          </div>
        )}

        {/* ── Config ── */}
        {tab === "config" && (
          <div className="tab-panel">
            {integrationView ? (
              <section
                style={{
                  marginBottom: "1.5rem",
                  padding: "1rem 1.15rem",
                  background: "var(--bg-base)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                  <div>
                    <h2 style={{ margin: "0 0 0.35rem", fontSize: "1.05rem", fontWeight: 700 }}>
                      Live config (portal API)
                    </h2>
                    <p className="lead" style={{ margin: 0, fontSize: "0.82rem" }}>
                      From <code style={{ fontSize: "0.78rem" }}>/portal/companies/…/config/overview</code>
                      {portalOverview && (
                        <>
                          {" · "}
                          Updated{" "}
                          <time dateTime={portalOverview.updated_at}>
                            {new Date(portalOverview.updated_at).toLocaleString()}
                          </time>
                        </>
                      )}
                      {!portalOverview && config?.updated_at && (
                        <>
                          {" · "}
                          Config updated{" "}
                          <time dateTime={config.updated_at}>
                            {new Date(config.updated_at).toLocaleString()}
                          </time>
                          {" "}
                          <span style={{ color: "var(--text-secondary)" }}>(overview partial — no WhatsApp channel row or full snapshot)</span>
                        </>
                      )}
                    </p>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "1rem",
                    marginTop: "1rem",
                  }}
                >
                  <div>
                    <h3 className="support-subhead" style={{ marginTop: 0 }}>Integration</h3>
                    <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.88rem", lineHeight: 1.5 }}>
                      <li>
                        Active provider: <code>{integrationView.whatsapp_provider ?? "—"}</code>
                      </li>
                      <li>
                        Weaviate: <code>{integrationView.weaviate_collection}</code>
                      </li>
                      <li>
                        Config active:{" "}
                        <span className={integrationView.is_active ? "badge badge--active" : "badge badge--inactive"}>
                          {integrationView.is_active ? "yes" : "no"}
                        </span>
                      </li>
                      {integrationView.whatsapp_channel_key && (
                        <li>
                          WhatsApp channel key: <code style={{ fontSize: "0.8rem" }}>{integrationView.whatsapp_channel_key}</code>
                        </li>
                      )}
                      <li>
                        Twilio sender (stored): <code>{integrationView.twilio_whatsapp_number ?? "—"}</code>
                        {integrationView.has_twilio_auth_token && (
                          <span style={{ marginLeft: "0.4em", color: "var(--success, #065f46)", fontSize: "0.8rem" }}>✓ token saved</span>
                        )}
                      </li>
                      <li>
                        AiSensy business number: <code>{integrationView.aisensy_whatsapp_number ?? "—"}</code>
                        {integrationView.aisensy_project_id != null && integrationView.aisensy_project_id !== "" && (
                          <span style={{ marginLeft: "0.4em", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            · project <code>{integrationView.aisensy_project_id}</code>
                          </span>
                        )}
                        {integrationView.has_aisensy_api_key && (
                          <span style={{ marginLeft: "0.4em", color: "var(--success, #065f46)", fontSize: "0.8rem" }}>✓ API key saved</span>
                        )}
                      </li>
                      <li>
                        Meta <code>phone_number_id</code>:{" "}
                        <code>
                          {"meta_phone_number_id" in integrationView
                            ? (integrationView.meta_phone_number_id ?? "—")
                            : "—"}
                        </code>
                        {"has_meta_graph_token" in integrationView
                          && integrationView.has_meta_graph_token && (
                          <span style={{ marginLeft: "0.4em", color: "var(--success, #065f46)", fontSize: "0.8rem" }}>✓ Graph token saved</span>
                        )}
                      </li>
                      <li>
                        Staff handoff WhatsApp alert:{" "}
                        {integrationView.handoff_staff_notify_configured ? (
                          <span className="badge badge--active">configured</span>
                        ) : (
                          <span style={{ color: "var(--text-secondary)" }}>not set</span>
                        )}
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h3 className="support-subhead" style={{ marginTop: 0 }}>Prompt &amp; languages</h3>
                    {portalOverview ? (
                      <>
                        <p style={{ margin: "0 0 0.35rem", fontSize: "0.88rem" }}>
                          Default: <strong>{portalOverview.prompt.default_language}</strong>
                          {" · "}
                          Supported: {portalOverview.prompt.supported_languages.join(", ")}
                        </p>
                        <p className="lead" style={{ margin: 0, fontSize: "0.82rem", maxHeight: "4.5rem", overflow: "auto" }}>
                          {(portalOverview.prompt.system_prompt || "(empty system prompt)").slice(0, 400)}
                          {(portalOverview.prompt.system_prompt?.length ?? 0) > 400 ? "…" : ""}
                        </p>
                      </>
                    ) : config ? (
                      <p className="lead" style={{ margin: 0, fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                        Default: <strong>{config.default_language}</strong>
                        {" · "}
                        Supported: {(config.supported_languages ?? []).join(", ")} — see form below for full prompt.
                      </p>
                    ) : (
                      <p className="lead" style={{ margin: 0, fontSize: "0.82rem" }}>—</p>
                    )}
                  </div>
                  <div>
                    <h3 className="support-subhead" style={{ marginTop: 0 }}>RAG — server defaults</h3>
                    {portalOverview ? (
                      <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "9rem", overflow: "auto" }}>
                        {jsonPrettyUi(portalOverview.rag.global_defaults)}
                      </pre>
                    ) : (
                      <p className="lead" style={{ margin: 0, fontSize: "0.82rem", color: "var(--text-secondary)" }}>Open when overview loads, or use RAG fields in the form.</p>
                    )}
                  </div>
                </div>

                <details style={{ marginTop: "1rem" }}>
                  <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: "0.9rem" }}>
                    Tenant JSON (RAG, fallback, handoff, business hours)
                  </summary>
                  <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.75rem" }}>
                    {portalOverview ? (
                      <>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            rag_config_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "10rem", overflow: "auto" }}>
                            {jsonPrettyUi(portalOverview.rag.rag_config_json ?? {})}
                          </pre>
                        </div>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            fallback_config_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "8rem", overflow: "auto" }}>
                            {jsonPrettyUi(portalOverview.escalation.fallback_config_json ?? {})}
                          </pre>
                        </div>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            handoff_config_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "8rem", overflow: "auto" }}>
                            {jsonPrettyUi(portalOverview.escalation.handoff_config_json ?? {})}
                          </pre>
                        </div>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            business_hours_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "6rem", overflow: "auto" }}>
                            {jsonPrettyUi(portalOverview.escalation.business_hours_json ?? {})}
                          </pre>
                        </div>
                      </>
                    ) : config ? (
                      <>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            rag_config_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "10rem", overflow: "auto" }}>
                            {jsonPrettyUi(config.rag_config_json ?? {})}
                          </pre>
                        </div>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            fallback_config_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "8rem", overflow: "auto" }}>
                            {jsonPrettyUi(config.fallback_config_json ?? {})}
                          </pre>
                        </div>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            handoff_config_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "8rem", overflow: "auto" }}>
                            {jsonPrettyUi(config.handoff_config_json ?? {})}
                          </pre>
                        </div>
                        <div>
                          <span className="support-subhead" style={{ display: "block", marginBottom: "0.35rem" }}>
                            business_hours_json
                          </span>
                          <pre className="support-pre" style={{ margin: 0, fontSize: "0.75rem", maxHeight: "6rem", overflow: "auto" }}>
                            {jsonPrettyUi(config.business_hours_json ?? {})}
                          </pre>
                        </div>
                      </>
                    ) : null}
                  </div>
                </details>
              </section>
            ) : (
              <p className="lead" style={{ marginBottom: "1rem", fontSize: "0.88rem", color: "var(--text-secondary)" }}>
                Overview API unavailable (check auth). You can still edit and save below.
              </p>
            )}

            <form className="stack" onSubmit={(e) => void saveConfig(e)}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <label>
                  <span>Default language</span>
                  <select value={defaultLang} onChange={(e) => setDefaultLang(e.target.value)}>
                    {langCatalog
                      .filter((o) => langs.includes(o.code))
                      .map((o) => (
                        <option key={o.code} value={o.code}>
                          {o.label}
                        </option>
                      ))}
                  </select>
                </label>
                <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.5rem 0.75rem" }}>
                  <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    Supported reply languages
                  </legend>
                  <p className="lead" style={{ margin: "0 0 0.5rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                    Bot may answer in any language you enable. Detection picks the closest match; users typing Roman Hindi need Hindi or Hinglish enabled.
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", paddingTop: "0.25rem" }}>
                    {langCatalog.map((o) => (
                      <label
                        key={o.code}
                        className="support-inline"
                        style={{
                          fontWeight: "normal",
                          fontSize: "0.9rem",
                          alignItems: "flex-start",
                          display: "flex",
                          gap: "0.5rem",
                          cursor: "pointer",
                        }}
                        title={o.description}
                      >
                        <input
                          type="checkbox"
                          style={{ marginTop: "0.2rem" }}
                          checked={langs.includes(o.code)}
                          onChange={() =>
                            setLangs((prev) => {
                              if (prev.includes(o.code)) {
                                if (prev.length <= 1) return prev;
                                return prev.filter((x) => x !== o.code);
                              }
                              return [...prev, o.code];
                            })
                          }
                        />
                        <span>
                          <strong style={{ display: "block" }}>{o.label}</strong>
                          <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                            {o.description}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              </div>

              <label>
                <span>System prompt</span>
                <textarea
                  rows={5}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Instructions for the model…"
                />
              </label>

              {/* ── RAG retrieval settings ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  RAG retrieval settings
                </legend>
                {portalOverview && (
                  <p style={{ margin: "0 0 0.75rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                    Server defaults — top_k: <strong>{portalOverview.rag.global_defaults.top_k}</strong> · score_threshold: <strong>{portalOverview.rag.global_defaults.score_threshold}</strong> · hybrid_alpha: <strong>{portalOverview.rag.global_defaults.hybrid_alpha}</strong>. Leave blank to use server default.
                  </p>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                  <label>
                    <span>Top K results</span>
                    <input
                      type="number" min={1} max={20} step={1}
                      placeholder={String(portalOverview?.rag.global_defaults.top_k ?? 5)}
                      value={ragTopK}
                      onChange={(e) => setRagTopK(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                  </label>
                  <label>
                    <span>Score threshold (0–1)</span>
                    <input
                      type="number" min={0} max={1} step={0.05}
                      placeholder={String(portalOverview?.rag.global_defaults.score_threshold ?? 0.4)}
                      value={ragScoreThreshold}
                      onChange={(e) => setRagScoreThreshold(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                  </label>
                  <label>
                    <span>Hybrid alpha (0=BM25 · 1=vector)</span>
                    <input
                      type="number" min={0} max={1} step={0.1}
                      placeholder={String(portalOverview?.rag.global_defaults.hybrid_alpha ?? 0.5)}
                      value={ragHybridAlpha}
                      onChange={(e) => setRagHybridAlpha(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                  </label>
                </div>
                <label style={{ marginTop: "0.75rem", display: "block" }}>
                  <span>Confidence strategy</span>
                  <select value={ragStrategy} onChange={(e) => setRagStrategy(e.target.value)}>
                    <option value="top">top — fallback if best score is below threshold (default)</option>
                    <option value="avg_top_k">avg_top_k — fallback if average of top-k is below threshold</option>
                    <option value="any_above">any_above — proceed if any score meets the threshold</option>
                  </select>
                </label>
              </fieldset>

              {/* ── Fallback messages ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Fallback messages (when bot has no answer)
                </legend>
                <p style={{ margin: "0 0 0.75rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                  Sent when retrieval confidence is too low. Leave blank to use built-in defaults.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
                  <label>
                    <span>English</span>
                    <textarea rows={2} value={fallbackEnglish} onChange={(e) => setFallbackEnglish(e.target.value)} placeholder="I'm sorry, I couldn't find relevant information to answer your question." />
                  </label>
                  <label>
                    <span>Hindi (हिंदी)</span>
                    <textarea rows={2} value={fallbackHindi} onChange={(e) => setFallbackHindi(e.target.value)} placeholder="माफ करें, मुझे आपके प्रश्न का उत्तर देने के लिए पर्याप्त जानकारी नहीं मिली।" />
                  </label>
                  <label>
                    <span>Hinglish</span>
                    <textarea rows={2} value={fallbackHinglish} onChange={(e) => setFallbackHinglish(e.target.value)} placeholder="Sorry, aapke question ka jawab dene ke liye relevant information nahi mili." />
                  </label>
                </div>
              </fieldset>

              {/* ── Handoff / escalation settings ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Handoff / escalation settings
                </legend>
                <p style={{ margin: "0 0 0.75rem", fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.45 }}>
                  When someone asks for a human, agent, or customer representative (built-in phrases plus your keywords below),
                  the bot switches that chat to agent mode. Optionally ping a separate staff WhatsApp number with the customer&apos;s number and what they said — set it under &quot;Staff handoff alert WhatsApp&quot;.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <label>
                    <span>Human-request keywords <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>(comma-separated, added on top of built-in phrases)</span></span>
                    <input
                      type="text"
                      placeholder="escalate, speak to human, agent please"
                      value={handoffKeywordsStr}
                      onChange={(e) => setHandoffKeywordsStr(e.target.value)}
                    />
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", alignItems: "end" }}>
                    <label
                      style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", cursor: "pointer", userSelect: "none", fontWeight: "normal" }}
                    >
                      <input
                        type="checkbox"
                        checked={handoffOnLowConf}
                        onChange={(e) => setHandoffOnLowConf(e.target.checked)}
                        style={{ marginTop: "0.2rem", width: 16, height: 16, flexShrink: 0 }}
                      />
                      <span>
                        <strong>Escalate on low confidence</strong>
                        <span style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: "normal" }}>
                          Trigger a handoff when the RAG score falls below the threshold.
                        </span>
                      </span>
                    </label>
                    <label>
                      <span>Low-confidence threshold (0–1)</span>
                      <input
                        type="number" min={0} max={1} step={0.05}
                        placeholder="0.2"
                        value={handoffLowConfThreshold}
                        disabled={!handoffOnLowConf}
                        onChange={(e) => setHandoffLowConfThreshold(e.target.value === "" ? "" : Number(e.target.value))}
                      />
                    </label>
                  </div>
                  <div>
                    <p style={{ margin: "0 0 0.5rem", fontSize: "0.82rem", fontWeight: 600 }}>
                      Handoff acknowledgement messages <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>(sent to customer when escalation is created)</span>
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      <label>
                        <span>English</span>
                        <input type="text" value={handoffAckEnglish} onChange={(e) => setHandoffAckEnglish(e.target.value)} placeholder="I'm connecting you to a human agent. Please wait a moment." />
                      </label>
                      <label>
                        <span>Hindi (हिंदी)</span>
                        <input type="text" value={handoffAckHindi} onChange={(e) => setHandoffAckHindi(e.target.value)} placeholder="मैं आपको एक मानव एजेंट से जोड़ रहा हूँ।" />
                      </label>
                      <label>
                        <span>Hinglish</span>
                        <input type="text" value={handoffAckHinglish} onChange={(e) => setHandoffAckHinglish(e.target.value)} placeholder="Aapko ek human agent se connect kar raha hoon." />
                      </label>
                    </div>
                  </div>
                  <div
                    style={{
                      borderTop: "1px solid var(--border)",
                      marginTop: "0.25rem",
                      paddingTop: "0.85rem",
                    }}
                  >
                    <p style={{ margin: "0 0 0.5rem", fontSize: "0.82rem", fontWeight: 600 }}>
                      Staff handoff alert WhatsApp
                    </p>
                    <label style={{ margin: 0 }}>
                      <span style={{ fontWeight: 400, color: "var(--text-secondary)", fontSize: "0.82rem" }}>
                        Second number (supervisor / on-call) — receives one WhatsApp message per <em>new</em> handoff with the customer&apos;s WhatsApp ID and their message context.
                      </span>
                      <input
                        type="text"
                        placeholder="+91 98765 43210"
                        value={handoffStaffNotifyWhatsapp}
                        onChange={(e) => setHandoffStaffNotifyWhatsapp(e.target.value)}
                        autoComplete="off"
                        style={{ marginTop: "0.45rem" }}
                      />
                    </label>
                    <p className="lead" style={{ marginTop: "0.4rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                      Enter the full international number (country code + number). Spaces and dashes are fine — we save it as <code style={{ fontSize: "0.85em" }}>whatsapp:+…</code>. Sends via your active WhatsApp integration (Twilio, AiSensy, or Meta — see the WhatsApp tab). Clear the field and save to turn alerts off.
                    </p>
                  </div>
                </div>
              </fieldset>

              {/* ── Business hours ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Business hours
                </legend>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "0.75rem" }}>
                  <label>
                    <span>Timezone</span>
                    <input type="text" placeholder="Asia/Kolkata" value={bhTimezone} onChange={(e) => setBhTimezone(e.target.value)} />
                  </label>
                  <label>
                    <span>Out-of-hours message</span>
                    <input type="text" placeholder="We're closed. We'll respond during business hours." value={bhOutOfHoursMsg} onChange={(e) => setBhOutOfHoursMsg(e.target.value)} />
                  </label>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                  {(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as const).map((day) => {
                    const d = bhSchedule[day]!;
                    return (
                      <div key={day} style={{ display: "grid", gridTemplateColumns: "130px 110px 110px auto", gap: "0.5rem", alignItems: "center" }}>
                        <label style={{ display: "flex", gap: "0.45rem", alignItems: "center", cursor: "pointer", userSelect: "none", fontWeight: d.enabled ? 600 : 400, margin: 0 }}>
                          <input
                            type="checkbox"
                            checked={d.enabled}
                            onChange={(e) => setBhSchedule((prev) => ({ ...prev, [day]: { ...prev[day]!, enabled: e.target.checked } }))}
                            style={{ width: 14, height: 14, flexShrink: 0 }}
                          />
                          <span style={{ textTransform: "capitalize" }}>{day}</span>
                        </label>
                        <label style={{ margin: 0 }}>
                          <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>Open</span>
                          <input
                            type="time" value={d.open} disabled={!d.enabled}
                            onChange={(e) => setBhSchedule((prev) => ({ ...prev, [day]: { ...prev[day]!, open: e.target.value } }))}
                            style={{ padding: "0.2rem 0.4rem", fontSize: "0.82rem" }}
                          />
                        </label>
                        <label style={{ margin: 0 }}>
                          <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>Close</span>
                          <input
                            type="time" value={d.close} disabled={!d.enabled}
                            onChange={(e) => setBhSchedule((prev) => ({ ...prev, [day]: { ...prev[day]!, close: e.target.value } }))}
                            style={{ padding: "0.2rem 0.4rem", fontSize: "0.82rem" }}
                          />
                        </label>
                        {!d.enabled && <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Closed</span>}
                      </div>
                    );
                  })}
                </div>
              </fieldset>

              <label>
                <span>WhatsApp: auto-resume after manual messaging (minutes)</span>
                <input
                  type="number"
                  min={0}
                  max={1440}
                  value={agentInactivityMinutes}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === "") {
                      setAgentInactivityMinutes("");
                      return;
                    }
                    const n = Number(v);
                    if (Number.isFinite(n)) setAgentInactivityMinutes(n);
                  }}
                  placeholder="15"
                />
                <p className="lead" style={{ marginTop: "0.35rem", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  When you message customers from the connected WhatsApp number, the bot pauses. After this many minutes without any further manual messages, it resumes replying automatically.
                </p>
              </label>

              <label>
                <span>Active WhatsApp provider</span>
                <select
                  value={whatsAppProvider}
                  onChange={(e) => setWhatsAppProvider(e.target.value as WhatsAppProvider)}
                >
                  <option value="twilio">Twilio</option>
                  <option value="aisensy">AiSensy</option>
                  <option value="meta">Meta Cloud API</option>
                </select>
                <p className="lead" style={{ marginTop: "0.35rem", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  Stored when you click <strong>Save configuration</strong> below. Configure credentials in the sections below; saving a provider&apos;s admin form also sets it active.
                </p>
              </label>

              {/* ── Twilio WhatsApp ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Twilio WhatsApp
                </legend>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <label>
                    <span>WhatsApp sender number</span>
                    <input
                      type="text"
                      placeholder="whatsapp:+14155238886"
                      value={twilioWhatsAppNumber}
                      onChange={(e) => setTwilioWhatsAppNumber(e.target.value)}
                    />
                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      Twilio sender number in <code>whatsapp:+&lt;E.164&gt;</code> format (e.g. <code>whatsapp:+14155238886</code> for the Sandbox, or your verified Business number).
                    </span>
                  </label>

                  <div style={{ padding: "0.6rem 0.75rem", background: "var(--bg-muted, #f9fafb)", borderRadius: "var(--radius-xs, 4px)", border: "1px solid var(--border)" }}>
                    <p style={{ margin: "0 0 0.3rem", fontSize: "0.8rem", fontWeight: 600 }}>
                      Configure in Twilio Console:
                    </p>
                    <p style={{ margin: "0 0 0.35rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                      In your Twilio WhatsApp Sandbox (or phone number) settings, set <strong>When a message comes in</strong> to:
                    </p>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <code style={{ fontSize: "0.77rem", wordBreak: "break-all", flex: 1 }}>
                        {TWILIO_INBOUND_WEBHOOK_URL}
                      </code>
                      <button
                        type="button"
                        style={{ flexShrink: 0, fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                        onClick={() => {
                          void navigator.clipboard.writeText(TWILIO_INBOUND_WEBHOOK_URL);
                          toast.success("Webhook URL copied.");
                        }}
                      >
                        Copy
                      </button>
                    </div>
                    <p style={{ margin: "0.4rem 0 0", fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                      HTTP method: <strong>POST</strong>. Each company uses its own Twilio account — set credentials below.
                    </p>
                  </div>

                  {/* ── Per-company Twilio credentials ── */}
                  <div style={{ padding: "0.75rem 0.9rem", background: "var(--bg-base)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}>
                    <p style={{ margin: "0 0 0.25rem", fontSize: "0.88rem", fontWeight: 700 }}>
                      Twilio credentials
                      {twilioHasSavedToken && (
                        <span style={{ marginLeft: "0.6em", fontWeight: 400, fontSize: "0.8rem", color: "var(--success, #065f46)" }}>
                          ✓ Auth token saved
                        </span>
                      )}
                    </p>
                    <p style={{ margin: "0 0 0.75rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                      Account SID and Auth Token are stored encrypted per-company. Required to send and receive messages.
                    </p>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                      <label>
                        <span>Account SID</span>
                        <input
                          type="text"
                          placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                          value={twilioAccountSid}
                          onChange={(e) => setTwilioAccountSid(e.target.value)}
                          autoComplete="off"
                        />
                      </label>
                      <label>
                        <span>Auth Token</span>
                        <input
                          type="password"
                          placeholder={twilioHasSavedToken ? "(stored — paste new value to replace)" : "your_auth_token"}
                          value={twilioAuthToken}
                          onChange={(e) => setTwilioAuthToken(e.target.value)}
                          autoComplete="new-password"
                        />
                      </label>
                    </div>
                    {twilioCredErr && <p className="error" style={{ marginTop: "0.5rem" }}>{twilioCredErr}</p>}
                    {twilioCredOk && <p className="success-inline" style={{ marginTop: "0.5rem" }}>{twilioCredOk}</p>}
                    <button
                      type="button"
                      className="primary"
                      disabled={twilioCredBusy || !twilioAccountSid.trim() || !twilioAuthToken.trim() || !twilioWhatsAppNumber.trim()}
                      style={{ marginTop: "0.75rem" }}
                      title={!twilioWhatsAppNumber.trim() ? "Fill in the sender number above first" : undefined}
                      onClick={() => {
                        setTwilioCredBusy(true);
                        setTwilioCredErr(null);
                        setTwilioCredOk(null);
                        void (async () => {
                          try {
                            const result = await saveTwilioConfig(accessToken, companyId, {
                              twilio_whatsapp_number: twilioWhatsAppNumber.trim(),
                              twilio_account_sid: twilioAccountSid.trim(),
                              twilio_auth_token: twilioAuthToken,
                              enable_twilio_provider: true,
                            });
                            setTwilioHasSavedToken(result.has_twilio_auth_token);
                            setTwilioAccountSid(result.twilio_account_sid ?? "");
                            setTwilioAuthToken("");
                            setTwilioCredOk("Twilio credentials saved and encrypted.");
                            setWhatsAppProvider("twilio");
                            toast.success("Twilio credentials saved and encrypted.");
                          } catch (e) {
                            const msg = e instanceof Error ? e.message : "Save failed";
                            setTwilioCredErr(msg);
                            toast.error(msg);
                          } finally {
                            setTwilioCredBusy(false);
                          }
                        })();
                      }}
                    >
                      {twilioCredBusy ? "Saving…" : "Save Twilio credentials"}
                    </button>
                  </div>
                </div>
              </fieldset>

              {/* ── AiSensy WhatsApp (admin API key) ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  AiSensy (Project API)
                </legend>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <p className="lead" style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    Uses your AiSensy business WhatsApp id and project API key. Requires <code>X-Admin-Key</code> (same as Twilio save). Inbound webhooks: POST below.
                  </p>
                  <div style={{ padding: "0.6rem 0.75rem", background: "var(--bg-muted, #f9fafb)", borderRadius: "var(--radius-xs, 4px)", border: "1px solid var(--border)" }}>
                    <p style={{ margin: "0 0 0.3rem", fontSize: "0.8rem", fontWeight: 600 }}>Set this URL in the AiSensy / Meta app webhook (POST)</p>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <code style={{ fontSize: "0.77rem", wordBreak: "break-all", flex: 1 }}>{AISENSY_INBOUND_WEBHOOK_URL}</code>
                      <button
                        type="button"
                        style={{ flexShrink: 0, fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                        onClick={() => {
                          void navigator.clipboard.writeText(AISENSY_INBOUND_WEBHOOK_URL);
                          toast.success("AiSensy webhook URL copied.");
                        }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                  <label>
                    <span>AiSensy business WhatsApp number</span>
                    <input
                      type="text"
                      placeholder="whatsapp:+918888888888"
                      value={aisensyWhatsappNumber}
                      onChange={(e) => setAisensyWhatsappNumber(e.target.value)}
                    />
                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      Must start with <code>whatsapp:</code> — must match the number used for webhook routing in AiSensy.
                    </span>
                  </label>
                  <label>
                    <span>Project id</span>
                    <input
                      type="text"
                      value={aisensyProjectId}
                      onChange={(e) => setAisensyProjectId(e.target.value)}
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    <span>Project API key (Bearer)</span>
                    <input
                      type="password"
                      placeholder={config?.has_aisensy_api_key ? "(stored — paste to replace or leave empty)" : "required for first save"}
                      value={aisensyApiKey}
                      onChange={(e) => setAisensyApiKey(e.target.value)}
                      autoComplete="new-password"
                    />
                  </label>
                  {aisensyErr && <p className="error" style={{ margin: 0 }}>{aisensyErr}</p>}
                  {aisensyOk && <p className="success-inline" style={{ margin: 0 }}>{aisensyOk}</p>}
                  <button
                    type="button"
                    className="primary"
                    disabled={
                      aisensyBusy
                      || !aisensyWhatsappNumber.trim().startsWith("whatsapp:")
                      || !aisensyProjectId.trim()
                      || (!aisensyApiKey.trim() && !config?.has_aisensy_api_key)
                    }
                    onClick={() => {
                      setAisensyBusy(true);
                      setAisensyErr(null);
                      setAisensyOk(null);
                      void (async () => {
                        try {
                          await saveAisensyConfig(accessToken, companyId, {
                            aisensy_whatsapp_number: aisensyWhatsappNumber.trim(),
                            aisensy_project_id: aisensyProjectId.trim(),
                            aisensy_api_key: aisensyApiKey.trim() || null,
                            enable_aisensy_provider: true,
                          });
                          setAisensyApiKey("");
                          setWhatsAppProvider("aisensy");
                          setAisensyOk("AiSensy saved. Active provider set to AiSensy.");
                          toast.success("AiSensy configuration saved.");
                          await loadAll();
                        } catch (e) {
                          const msg = e instanceof Error ? e.message : "Save failed";
                          setAisensyErr(msg);
                          toast.error(msg);
                        } finally {
                          setAisensyBusy(false);
                        }
                      })();
                    }}
                  >
                    {aisensyBusy ? "Saving…" : "Save AiSensy credentials"}
                  </button>
                </div>
              </fieldset>

              {/* ── Meta WhatsApp Cloud API ── */}
              <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "0.75rem 0.9rem" }}>
                <legend style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  Meta Cloud API (Graph)
                </legend>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <p className="lead" style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    Direct WhatsApp messaging via Meta&apos;s Cloud API. Use the <strong>phone number id</strong> from the WhatsApp product in Meta Business Suite / Developers. Requires <code>X-Admin-Key</code> to save.
                  </p>
                  <div style={{ padding: "0.6rem 0.75rem", background: "var(--bg-muted, #f9fafb)", borderRadius: "var(--radius-xs, 4px)", border: "1px solid var(--border)" }}>
                    <p style={{ margin: "0 0 0.3rem", fontSize: "0.8rem", fontWeight: 600 }}>Webhook URL (GET verify + POST)</p>
                    <p style={{ margin: "0 0 0.35rem", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                      In the Meta App → WhatsApp → Configuration, set the callback URL to:
                    </p>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <code style={{ fontSize: "0.77rem", wordBreak: "break-all", flex: 1 }}>{META_WHATSAPP_WEBHOOK_URL}</code>
                      <button
                        type="button"
                        style={{ flexShrink: 0, fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                        onClick={() => {
                          void navigator.clipboard.writeText(META_WHATSAPP_WEBHOOK_URL);
                          toast.success("Meta webhook URL copied.");
                        }}
                      >
                        Copy
                      </button>
                    </div>
                    <p style={{ margin: "0.4rem 0 0", fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                      Use the same <strong>Verify token</strong> you enter below (or set <code>META_WEBHOOK_VERIFY_TOKEN</code> on the server for a single shared webhook).
                    </p>
                  </div>
                  <label>
                    <span>Phone number ID</span>
                    <input
                      type="text"
                      placeholder="e.g. 1107448072457336"
                      value={metaPhoneNumberId}
                      onChange={(e) => setMetaPhoneNumberId(e.target.value)}
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    <span>WhatsApp Business Account ID (WABA)</span>
                    <input
                      type="text"
                      placeholder="e.g. 1348185130513488"
                      value={metaWabaId}
                      onChange={(e) => setMetaWabaId(e.target.value)}
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    <span>Graph API access token</span>
                    <input
                      type="password"
                      placeholder={config?.has_meta_graph_token ? "(stored — paste to replace)" : "EAA… long-lived user token"}
                      value={metaGraphToken}
                      onChange={(e) => setMetaGraphToken(e.target.value)}
                      autoComplete="new-password"
                    />
                  </label>
                  <label>
                    <span>App secret (optional, recommended)</span>
                    <input
                      type="password"
                      placeholder={config?.has_meta_app_secret ? "(stored — paste to replace)" : "for X-Hub-Signature-256"}
                      value={metaAppSecret}
                      onChange={(e) => setMetaAppSecret(e.target.value)}
                      autoComplete="new-password"
                    />
                  </label>
                  <label>
                    <span>Webhook verify token</span>
                    <input
                      type="password"
                      placeholder={config?.has_meta_webhook_verify_token ? "(stored — paste to replace)" : "custom string for Meta GET verify"}
                      value={metaWebhookVerifyToken}
                      onChange={(e) => setMetaWebhookVerifyToken(e.target.value)}
                      autoComplete="new-password"
                    />
                  </label>
                  {metaErr && <p className="error" style={{ margin: 0 }}>{metaErr}</p>}
                  {metaOk && <p className="success-inline" style={{ margin: 0 }}>{metaOk}</p>}
                  <button
                    type="button"
                    className="primary"
                    disabled={
                      metaBusy
                      || !metaPhoneNumberId.trim()
                      || (!metaGraphToken.trim() && !config?.has_meta_graph_token)
                      || (!metaWebhookVerifyToken.trim() && !config?.has_meta_webhook_verify_token)
                    }
                    onClick={() => {
                      setMetaBusy(true);
                      setMetaErr(null);
                      setMetaOk(null);
                      void (async () => {
                        try {
                          await saveMetaWhatsappConfig(accessToken, companyId, {
                            meta_phone_number_id: metaPhoneNumberId.trim(),
                            meta_waba_id: metaWabaId.trim() || null,
                            meta_graph_access_token: metaGraphToken.trim() || null,
                            meta_app_secret: metaAppSecret.trim() || null,
                            meta_webhook_verify_token: metaWebhookVerifyToken.trim() || null,
                            enable_meta_provider: true,
                          });
                          setMetaGraphToken("");
                          setMetaAppSecret("");
                          setMetaWebhookVerifyToken("");
                          setWhatsAppProvider("meta");
                          setMetaOk("Meta Cloud API saved. Active provider set to Meta.");
                          toast.success("Meta WhatsApp configuration saved.");
                          await loadAll();
                        } catch (e) {
                          const msg = e instanceof Error ? e.message : "Save failed";
                          setMetaErr(msg);
                          toast.error(msg);
                        } finally {
                          setMetaBusy(false);
                        }
                      })();
                    }}
                  >
                    {metaBusy ? "Saving…" : "Save Meta Cloud API credentials"}
                  </button>
                </div>
              </fieldset>

              <label
                className="support-inline"
                style={{ display: "flex", alignItems: "center", gap: "0.6rem", cursor: "pointer", userSelect: "none" }}
              >
                <input
                  type="checkbox"
                  checked={configActive}
                  onChange={(e) => setConfigActive(e.target.checked)}
                  style={{ width: 16, height: 16 }}
                />
                <span>
                  <strong>Config active</strong>
                  <span style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: "normal" }}>
                    Uncheck to pause the bot for this company without deactivating the company account.
                  </span>
                </span>
              </label>

              <fieldset className="stack" style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "1rem" }}>
                <legend style={{ fontWeight: 700, padding: "0 0.35rem" }}>
                  Google Sheet sync
                </legend>
                <label
                  className="support-inline"
                  style={{ display: "flex", alignItems: "center", gap: "0.6rem", cursor: "pointer", userSelect: "none" }}
                >
                  <input
                    type="checkbox"
                    checked={googleSheetsEnabled}
                    onChange={(e) => setGoogleSheetsEnabled(e.target.checked)}
                    style={{ width: 16, height: 16 }}
                  />
                  <span>
                    <strong>Live sheet enabled</strong>
                    <span style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: "normal" }}>
                      New inbox messages and lead status changes sync when backend Google credentials are configured.
                    </span>
                  </span>
                </label>
                <label>
                  <span>Spreadsheet ID</span>
                  <input
                    type="text"
                    value={googleSheetId}
                    onChange={(e) => setGoogleSheetId(e.target.value)}
                    placeholder="Leave blank to auto-create on first sync"
                  />
                </label>
                {config?.google_sheet_url && (
                  <a href={config.google_sheet_url} target="_blank" rel="noreferrer">
                    Open live Google Sheet
                  </a>
                )}
              </fieldset>

              {config && (
                <p className="lead" style={{ fontSize: "0.82rem" }}>
                  Active provider:{" "}
                  <code style={{ background: "var(--accent-soft, #eff6ff)", color: "var(--accent)", padding: "0.1em 0.35em", borderRadius: "3px" }}>
                    {config.whatsapp_provider || whatsAppProvider}
                  </code>
                  {" · "}
                  Weaviate: <code>{config.weaviate_collection}</code>
                  {" · "}
                  Twilio: <code>{config.twilio_whatsapp_number || twilioWhatsAppNumber || "—"}</code>
                  {" · "}
                  AiSensy: <code>{config.aisensy_whatsapp_number || aisensyWhatsappNumber || "—"}</code>
                  {" · "}
                  Meta phone_number_id: <code>{config.meta_phone_number_id || metaPhoneNumberId || "—"}</code>
                </p>
              )}

              <div>
                <button className="primary" type="submit" disabled={busy}>
                  Save configuration
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── Documents ── */}
        {tab === "documents" && (
          <div className="tab-panel">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
              <p className="lead" style={{ margin: 0 }}>
                {docs ? `${docs.total} document${docs.total !== 1 ? "s" : ""}` : "Loading…"}
              </p>
              <label
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.55rem 1rem",
                  background: "var(--accent)",
                  color: "#fff",
                  borderRadius: "var(--radius-sm)",
                  cursor: busy ? "not-allowed" : "pointer",
                  fontWeight: 600,
                  fontSize: "0.9rem",
                  opacity: busy ? 0.55 : 1,
                }}
              >
                Upload file
                <input
                  type="file"
                  disabled={busy}
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    void run(async () => {
                      await uploadDocument(accessToken, companyId, f);
                      toast.success("Uploaded successfully.");
                      await loadAll();
                      e.target.value = "";
                    });
                  }}
                />
              </label>
            </div>

            {docs && docs.documents.length === 0 && (
              <p className="lead" style={{ textAlign: "center", padding: "2rem" }}>No documents yet. Upload a file to get started.</p>
            )}

            {docs && docs.documents.length > 0 && (
              <div className="table-scroll">
              <table className="companies">
                <thead>
                  <tr>
                    <th>File name</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {docs.documents.map((d) => (
                    <tr key={d.id}>
                      <td style={{ fontWeight: 500 }}>{d.file_name}</td>
                      <td>
                        <span className={`badge ${d.status === "indexed" ? "badge--active" : d.status === "pending" ? "badge--draft" : "badge--inactive"}`}>
                          {d.status}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy}
                          onClick={() => void run(async () => {
                            await reindexDocument(accessToken, companyId, d.id);
                            toast.success("Re-index queued.");
                            await loadAll();
                          })}
                        >
                          Re-index
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </div>
        )}

        {/* ── Products ── */}
        {tab === "products" && (
          <div className="tab-panel">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
              <p className="lead" style={{ margin: 0 }}>
                {productTotal} product{productTotal !== 1 ? "s" : ""}
              </p>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => void run(async () => {
                    const res = await reindexAllProducts(accessToken, companyId) as BulkReindexResponse;
                    toast.success(res.message);
                    const pl = await listProducts(accessToken, companyId);
                    setProducts(pl.products);
                    setProductTotal(pl.total);
                  })}
                >
                  Reindex all
                </button>
                <button
                  type="button"
                  className="primary"
                  disabled={busy}
                  onClick={() => {
                    setProductForm({ name: "", synonyms: [], is_active: true });
                    setProductPriceStr("{}");
                    setProductAttrsStr("{}");
                    setProductSynonymsStr("");
                    setProductImageUrl("");
                    setProductImageAlt("");
                    setProductFormOpen(true);
                  }}
                >
                  + Add product
                </button>
              </div>
            </div>

            {/* Create / edit form */}
            {productFormOpen && (
              <div
                style={{
                  marginTop: "1rem",
                  padding: "1.25rem",
                  background: "var(--bg-base)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 700 }}>
                  {productForm.id ? "Edit product" : "New product"}
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label>
                    <span>Name *</span>
                    <input
                      type="text"
                      value={productForm.name}
                      onChange={(e) => setProductForm((p) => ({ ...p, name: e.target.value }))}
                      placeholder="Product name"
                    />
                  </label>
                  <label>
                    <span>SKU</span>
                    <input
                      type="text"
                      value={productForm.sku ?? ""}
                      onChange={(e) => setProductForm((p) => ({ ...p, sku: e.target.value || null }))}
                      placeholder="ACC-001"
                    />
                  </label>
                  <label>
                    <span>Category</span>
                    <input
                      type="text"
                      value={productForm.category ?? ""}
                      onChange={(e) => setProductForm((p) => ({ ...p, category: e.target.value || null }))}
                      placeholder="Electronics, Accessories…"
                    />
                  </label>
                  <label className="support-inline" style={{ alignItems: "center", gap: "0.5rem", display: "flex", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={productForm.is_active ?? true}
                      onChange={(e) => setProductForm((p) => ({ ...p, is_active: e.target.checked }))}
                      style={{ width: 16, height: 16 }}
                    />
                    <span>Active</span>
                  </label>
                  <label>
                    <span>Image URL</span>
                    <input
                      type="url"
                      value={productImageUrl}
                      onChange={(e) => setProductImageUrl(e.target.value)}
                      placeholder="https://example.com/product.jpg"
                    />
                  </label>
                  <label>
                    <span>Image alt</span>
                    <input
                      type="text"
                      value={productImageAlt}
                      onChange={(e) => setProductImageAlt(e.target.value)}
                      placeholder={productForm.name || "Product name"}
                    />
                  </label>
                </div>
                {productImageUrl.trim() && (
                  <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center" }}>
                    <img
                      src={productImageUrl.trim()}
                      alt={productImageAlt.trim() || productForm.name || "Product image"}
                      style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg-muted)" }}
                    />
                  </div>
                )}
                <label style={{ marginTop: "0.75rem", display: "block" }}>
                  <span>Description (gets embedded for RAG search)</span>
                  <textarea
                    rows={4}
                    value={productForm.description ?? ""}
                    onChange={(e) => setProductForm((p) => ({ ...p, description: e.target.value || null }))}
                    placeholder="Full product description…"
                  />
                </label>
                <label style={{ marginTop: "0.75rem", display: "block" }}>
                  <span>Synonyms</span>
                  <textarea
                    rows={3}
                    value={productSynonymsStr}
                    onChange={(e) => setProductSynonymsStr(e.target.value)}
                    placeholder={"neend ki dawa\nnind medicine\nsleep capsule"}
                  />
                  <small style={{ color: "var(--text-muted)" }}>
                    Add alternate names, rural phrases, Hindi/Hinglish words, and spelling variants. Use comma or new line.
                  </small>
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginTop: "0.75rem" }}>
                  <label>
                    <span>Price JSON</span>
                    <textarea
                      rows={3}
                      className="support-mono"
                      value={productPriceStr}
                      onChange={(e) => setProductPriceStr(e.target.value)}
                      placeholder='{"amount": 999, "currency": "INR"}'
                    />
                  </label>
                  <label>
                    <span>Attributes JSON</span>
                    <textarea
                      rows={3}
                      className="support-mono"
                      value={productAttrsStr}
                      onChange={(e) => setProductAttrsStr(e.target.value)}
                      placeholder='{"color": "Silver", "warranty": "1 year"}'
                    />
                  </label>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={busy || !productForm.name.trim()}
                    onClick={() => void run(async () => {
                      let price: Record<string, unknown> | null = null;
                      let attrs: Record<string, unknown> | null = null;
                      try {
                        price = productPriceStr.trim() && productPriceStr !== "{}" ? JSON.parse(productPriceStr) as Record<string, unknown> : null;
                        attrs = productAttrsStr.trim() && productAttrsStr !== "{}" ? JSON.parse(productAttrsStr) as Record<string, unknown> : null;
                      } catch {
                        const msg = "Invalid JSON in price or attributes.";
                        setErr(msg);
                        toast.error(msg);
                        return;
                      }
                      attrs = mergeProductImageAttrs(attrs, productImageUrl, productImageAlt, productForm.name);
                      if (productForm.id) {
                        await updateProduct(accessToken, companyId, productForm.id, {
                          ...productForm,
                          price_json: price,
                          attributes_json: attrs,
                          synonyms: parseSynonymsText(productSynonymsStr),
                        });
                      } else {
                        // Backend auto-indexes on create; no separate reindex call needed
                        await createProduct(accessToken, companyId, {
                          ...productForm,
                          price_json: price,
                          attributes_json: attrs,
                          synonyms: parseSynonymsText(productSynonymsStr),
                        });
                      }
                      const pl = await listProducts(accessToken, companyId);
                      setProducts(pl.products);
                      setProductTotal(pl.total);
                      setProductFormOpen(false);
                      toast.success(productForm.id ? "Product updated." : "Product created (auto-indexed).");
                    })}
                  >
                    {productForm.id ? "Save changes" : "Create & index"}
                  </button>
                  <button type="button" className="secondary" onClick={() => setProductFormOpen(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Product list */}
            {products.length === 0 && !productFormOpen && (
              <p className="lead" style={{ textAlign: "center", padding: "2rem" }}>
                No products yet. Click <strong>+ Add product</strong> to get started.
              </p>
            )}
            {products.length > 0 && (
              <div className="table-scroll table-scroll--wide" style={{ marginTop: "1rem" }}>
              <table className="companies">
                <thead>
                  <tr>
                    <th>Image</th>
                    <th>Name</th>
                    <th>SKU</th>
                    <th>Category</th>
                    <th>Synonyms</th>
                    <th>Price</th>
                    <th>Indexed</th>
                    <th>Active</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr key={p.id}>
                      <td>
                        {getProductImageUrl(p) ? (
                          <img
                            src={getProductImageUrl(p)}
                            alt={getProductImageAlt(p)}
                            style={{ width: 44, height: 44, objectFit: "cover", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-muted)" }}
                          />
                        ) : (
                          "—"
                        )}
                      </td>
                      <td style={{ fontWeight: 500 }}>{p.name}</td>
                      <td><code style={{ fontSize: "0.78rem" }}>{p.sku ?? "—"}</code></td>
                      <td>{p.category ?? "—"}</td>
                      <td style={{ fontSize: "0.82rem", maxWidth: 260 }}>
                        {p.synonyms && p.synonyms.length > 0
                          ? `${p.synonyms.slice(0, 3).join(", ")}${p.synonyms.length > 3 ? ` +${p.synonyms.length - 3}` : ""}`
                          : "—"}
                      </td>
                      <td style={{ fontSize: "0.82rem" }}>
                        {p.price_json
                          ? `${(p.price_json as Record<string, unknown>)["currency"] ?? ""} ${(p.price_json as Record<string, unknown>)["amount"] ?? ""}`.trim()
                          : "—"}
                      </td>
                      <td>
                        <span className={`badge ${p.weaviate_indexed ? "badge--active" : "badge--draft"}`}>
                          {p.weaviate_indexed ? "yes" : "no"}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${p.is_active ? "badge--active" : "badge--inactive"}`}>
                          {p.is_active ? "active" : "inactive"}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            onClick={() => {
                              setProductForm({
                                id: p.id,
                                name: p.name,
                                sku: p.sku,
                                category: p.category,
                                description: p.description,
                                synonyms: p.synonyms ?? [],
                                is_active: p.is_active,
                              });
                              setProductPriceStr(jsonPretty(p.price_json ?? {}));
                              setProductAttrsStr(jsonPretty(p.attributes_json ?? {}));
                              setProductSynonymsStr(synonymsText(p.synonyms));
                              setProductImageUrl(getProductImageUrl(p));
                              setProductImageAlt(getProductImageAlt(p));
                              setProductFormOpen(true);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            onClick={() => void run(async () => {
                              const res = await reindexProduct(accessToken, companyId, p.id);
                              if (res.success) toast.success(`Indexed: ${p.name}`);
                              else toast.error(res.message || "Reindex failed");
                              const pl = await listProducts(accessToken, companyId);
                              setProducts(pl.products);
                              setProductTotal(pl.total);
                            })}
                          >
                            Reindex
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            style={{ color: "var(--danger)" }}
                            onClick={() => void run(async () => {
                              if (!confirm(`Delete product "${p.name}"?`)) return;
                              await deleteProduct(accessToken, companyId, p.id);
                              toast.success(`Deleted: ${p.name}`);
                              const pl = await listProducts(accessToken, companyId);
                              setProducts(pl.products);
                              setProductTotal(pl.total);
                            })}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </div>
        )}

        {/* ── WhatsApp ── */}
        {tab === "campaigns" && (
          <div className="tab-panel">
            <div className="grid-responsive" style={{ gap: "1rem" }}>
              <div>
                <h3 className="support-subhead" style={{ marginTop: 0 }}>Bulk advertising campaign</h3>
                <div className="support-card compact" style={{ marginBottom: "0.9rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "flex-start", flexWrap: "wrap" }}>
                    <div>
                      <p className="lead" style={{ margin: 0, fontWeight: 700 }}>Sample Meta template</p>
                      <p style={{ margin: "0.35rem 0 0", color: "var(--text-muted)" }}>
                        Use an approved Meta template whose body contains one variable, for example: {"{{1}}"}
                      </p>
                      <p style={{ margin: "0.45rem 0 0", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                        Excel only needs a <code>phone</code> column. Type the campaign message below and it is sent as template variable 1.
                      </p>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => {
                          downloadXlsx("campaign-sample.xlsx", { recipients: SAMPLE_CAMPAIGN_ROWS });
                          toast.success("Sample campaign Excel downloaded.");
                        }}
                      >
                        Download sample Excel
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => {
                          setCampaignName((current) => current || "Sample product offer");
                          setCampaignTemplate((current) => current || "campaign_text_template");
                          setCampaignLang((current) => current || "en_US");
                          setCampaignPhoneCol((current) => current || "phone");
                          setCampaignMessage("Hi, we have a new offer for you. Reply YES to know more.");
                          setCampaignVars("");
                          setCampaignHeaderMediaCol("");
                        }}
                      >
                        Use sample message
                      </button>
                    </div>
                  </div>
                </div>
                <label>
                  <span>Recipient Excel/CSV</span>
                  <input type="file" accept=".xlsx,.csv" onChange={(e) => setCampaignFile(e.target.files?.[0] ?? null)} />
                </label>
                <button type="button" className="secondary" disabled={busy || !campaignFile} style={{ marginTop: "0.6rem" }} onClick={() => void run(async () => {
                  if (!campaignFile) return;
                  const preview = await previewCampaignUpload(accessToken, companyId, campaignFile);
                  setCampaignPreview(preview);
                  const phoneCol = preview.columns.find((c) => ["phone", "phone_number", "mobile", "whatsapp", "number"].includes(c.toLowerCase())) || preview.columns[0] || "";
                  setCampaignPhoneCol(phoneCol);
                  toast.success(`Preview loaded: ${preview.valid_rows}/${preview.total_rows} valid rows.`);
                })}>Preview file</button>
                {campaignPreview && (
                  <div style={{ marginTop: "1rem" }}>
                    <p className="lead" style={{ margin: 0 }}>{campaignPreview.valid_rows} valid / {campaignPreview.total_rows} rows</p>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginTop: "0.75rem" }}>
                      <label><span>Campaign name</span><input value={campaignName} onChange={(e) => setCampaignName(e.target.value)} placeholder="May offers" /></label>
                      <label><span>Phone column</span><select value={campaignPhoneCol} onChange={(e) => setCampaignPhoneCol(e.target.value)}>{campaignPreview.columns.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
                      <label><span>Meta template name</span><input value={campaignTemplate} onChange={(e) => setCampaignTemplate(e.target.value)} placeholder="approved_template_name" /></label>
                      <label><span>Language code</span><input value={campaignLang} onChange={(e) => setCampaignLang(e.target.value)} placeholder="en_US" /></label>
                    </div>
                    <label style={{ display: "block", marginTop: "0.75rem" }}>
                      <span>Campaign message</span>
                      <textarea
                        value={campaignMessage}
                        onChange={(e) => setCampaignMessage(e.target.value)}
                        placeholder="Type the message that should go into template variable {{1}}"
                        rows={4}
                      />
                    </label>
                    <label style={{ display: "block", marginTop: "0.75rem" }}><span>Body variable columns (optional advanced)</span><input value={campaignVars} onChange={(e) => setCampaignVars(e.target.value)} placeholder="name, product, price" /></label>
                    <label style={{ display: "block", marginTop: "0.75rem" }}><span>Header media column (optional)</span><input value={campaignHeaderMediaCol} onChange={(e) => setCampaignHeaderMediaCol(e.target.value)} placeholder="image_url" /></label>
                    <button type="button" className="primary" disabled={busy || !campaignName.trim() || !campaignTemplate.trim() || !campaignPhoneCol} style={{ marginTop: "0.9rem" }} onClick={() => void run(async () => {
                      if (!campaignPreview) return;
                      const columnVariables = splitColumnsText(campaignVars);
                      const bodyVariableMappings: Array<string | Record<string, unknown>> = campaignMessage.trim()
                        ? [{ source: "literal", value: campaignMessage.trim() }, ...columnVariables]
                        : columnVariables;
                      const created = await createCampaign(accessToken, companyId, {
                        name: campaignName.trim(),
                        template_name: campaignTemplate.trim(),
                        language_code: campaignLang.trim() || "en",
                        phone_column: campaignPhoneCol,
                        body_variable_mappings: bodyVariableMappings,
                        header_media_url_mapping: campaignHeaderMediaCol.trim() || null,
                        rows: campaignPreview.rows.filter((r) => !r._error),
                      });
                      toast.success("Campaign created.");
                      setCampaigns(await listCampaigns(accessToken, companyId));
                      setOutboxJobs(await listOutboxJobs(accessToken, companyId, { campaignId: created.id }));
                      setCampaignPreview(null);
                      setCampaignFile(null);
                      setCampaignName("");
                      setCampaignTemplate("");
                      setCampaignVars("");
                      setCampaignMessage("");
                      setCampaignHeaderMediaCol("");
                    })}>Create campaign</button>
                    {campaignPreview.errors.length > 0 && <pre className="support-pre" style={{ marginTop: "0.75rem", maxHeight: 120 }}>{campaignPreview.errors.slice(0, 8).join("\n")}</pre>}
                  </div>
                )}
              </div>
            </div>
            <h3 className="support-subhead">Campaigns</h3>
            <div className="table-scroll table-scroll--wide">
              <table className="companies">
                <thead><tr><th>Name</th><th>Template</th><th>Status</th><th>Total</th><th>Queued</th><th>Sent</th><th>Failed</th><th /></tr></thead>
                <tbody>{campaigns.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td><td>{c.template_name}</td><td><span className={`badge ${c.status === "running" ? "badge--active" : c.status === "cancelled" ? "badge--inactive" : "badge--draft"}`}>{c.status}</span></td>
                    <td>{c.total_recipients}</td><td>{c.queued_count}</td><td>{c.sent_count}</td><td>{c.failed_count}</td>
                    <td><div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button className="secondary" disabled={busy || c.status === "running"} onClick={() => void run(async () => {
                        await campaignAction(accessToken, companyId, c.id, "start");
                        setCampaigns(await listCampaigns(accessToken, companyId));
                        setOutboxJobs(await listOutboxJobs(accessToken, companyId, { campaignId: c.id }));
                      })}>Start</button>
                      <button className="secondary" disabled={busy} onClick={() => void run(async () => {
                        await campaignAction(accessToken, companyId, c.id, "pause");
                        setCampaigns(await listCampaigns(accessToken, companyId));
                      })}>Pause</button>
                      <button className="secondary" disabled={busy} onClick={() => void run(async () => {
                        setOutboxJobs(await listOutboxJobs(accessToken, companyId, { campaignId: c.id }));
                      })}>Jobs</button>
                    </div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <h3 className="support-subhead">Recent outbox</h3>
            <div className="table-scroll table-scroll--wide">
              <table className="companies">
                <thead><tr><th>Kind</th><th>To</th><th>Template</th><th>Status</th><th>Attempts</th><th>Error</th></tr></thead>
                <tbody>{outboxJobs.slice(0, 30).map((j) => (
                  <tr key={j.id}><td>{j.kind}</td><td>{j.to_number}</td><td>{j.template_name}</td><td>{j.status}</td><td>{j.attempts}</td><td style={{ maxWidth: 360 }}>{j.last_error || "—"}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "followups" && (
          <div className="tab-panel">
            <div className="support-card compact" style={{ marginBottom: "1rem" }}>
              <h3 className="support-subhead" style={{ marginTop: 0 }}>Open-lead follow-ups</h3>
              <p className="lead" style={{ margin: 0, color: "var(--text-muted)", maxWidth: 720 }}>
                Pick an <strong>approved Meta template</strong> below — preview loads from Meta (copy edits happen in WhatsApp Manager).
                Inside the messaging window (~24h), an AI-written message is sent instead. Mark Inbox threads{" "}
                <strong>inquiry complete</strong> to stop automated follow-ups.
              </p>
            </div>
            <div className="grid-responsive" style={{ gap: "1rem", alignItems: "start" }}>
              <div>
                <h3 className="support-subhead" style={{ marginTop: 0 }}>Create rule</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label><span>Rule name</span><input value={followupName} onChange={(e) => setFollowupName(e.target.value)} placeholder="Open lead reminder" /></label>
                  <label><span>Delay minutes</span><input type="number" min={1} value={followupDelay} onChange={(e) => setFollowupDelay(Number(e.target.value || 1))} /></label>
                </div>
                <FollowupTemplatePicker
                  accessToken={accessToken}
                  companyId={companyId}
                  templateName={followupTemplate}
                  setTemplateName={setFollowupTemplate}
                  languageCode={followupLang}
                  setLanguageCode={setFollowupLang}
                  bodyVariablesCsv={followupBodyVarsCsv}
                  setBodyVariablesCsv={setFollowupBodyVarsCsv}
                />
                <button type="button" className="primary" disabled={busy || !followupName.trim() || !followupTemplate.trim()} style={{ marginTop: "0.9rem" }} onClick={() => void run(async () => {
                  await createFollowupRule(accessToken, companyId, {
                    name: followupName.trim(),
                    is_active: true,
                    steps: [{
                      delay_minutes: followupDelay,
                      template_name: followupTemplate.trim(),
                      language_code: followupLang.trim() || "en",
                      body_variables: parseFollowupBodyVariablesCsv(followupBodyVarsCsv),
                    }],
                  });
                  toast.success("Follow-up rule created.");
                  setFollowupRules(await listFollowupRules(accessToken, companyId));
                  setFollowupName("");
                  setFollowupTemplate("");
                  setFollowupBodyVarsCsv("");
                })}>Create follow-up rule</button>
              </div>
              <div>
                <h3 className="support-subhead" style={{ marginTop: 0 }}>How it works</h3>
                <div className="support-card compact">
                  <p>A rule sends after the configured delay from the customer&apos;s last message.</p>
                  <p>It only applies when <code>inquiry_complete</code> is false.</p>
                  <p>Inside ~24 hours of last customer activity, delivery is usually an AI-written session message; later, the configured Meta template is used instead.</p>
                  <p style={{ marginBottom: 0 }}>It is skipped if the customer replies again, opts out, or the rule is paused.</p>
                </div>
              </div>
            </div>
            <h3 className="support-subhead">Follow-up rules</h3>
            <div className="table-scroll">
              <table className="companies">
                <thead><tr><th>Rule</th><th>Delay</th><th>Template</th><th>Active</th><th /></tr></thead>
                <tbody>{followupRules.length === 0 ? (
                  <tr><td colSpan={5} style={{ color: "var(--text-muted)" }}>No follow-up rules yet.</td></tr>
                ) : followupRules.map((r) => {
                  const firstStep = r.steps_json[0] || {};
                  return (
                    <tr key={r.id}>
                      <td>{r.name}</td>
                      <td>{String(firstStep.delay_minutes ?? "-")} min</td>
                      <td>{String(firstStep.template_name ?? "-")}</td>
                      <td>{r.is_active ? "yes" : "no"}</td>
                      <td>
                        <button type="button" className="secondary" disabled={busy} onClick={() => void run(async () => {
                          await updateFollowupRule(accessToken, companyId, r.id, { is_active: !r.is_active });
                          setFollowupRules(await listFollowupRules(accessToken, companyId));
                        })}>{r.is_active ? "Pause" : "Enable"}</button>
                        <button type="button" className="secondary" disabled={busy} style={{ marginLeft: 6, color: "var(--danger)" }} onClick={() => void run(async () => {
                          await deleteFollowupRule(accessToken, companyId, r.id);
                          setFollowupRules(await listFollowupRules(accessToken, companyId));
                        })}>Delete</button>
                      </td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>
            <h3 className="support-subhead">Recent follow-up outbox</h3>
            <div className="table-scroll table-scroll--wide">
              <table className="companies">
                <thead><tr><th>To</th><th>Template</th><th>Status</th><th>Attempts</th><th>Error</th></tr></thead>
                <tbody>{outboxJobs.filter((j) => j.kind === "followup").slice(0, 30).map((j) => (
                  <tr key={j.id}><td>{j.to_number}</td><td>{j.template_name}</td><td>{j.status}</td><td>{j.attempts}</td><td style={{ maxWidth: 360 }}>{j.last_error || "—"}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "whatsapp" && (
          <div className="tab-panel">

            <p className="lead" style={{ margin: "0 0 1rem", fontSize: "0.88rem" }}>
              <strong>Active provider:</strong>{" "}
              <code style={{ background: "var(--accent-soft, #eff6ff)", color: "var(--accent)", padding: "0.1em 0.35em", borderRadius: "3px" }}>
                {config?.whatsapp_provider || "—"}
              </code>
              {" · "}
              <strong>Twilio sender:</strong> <code style={{ userSelect: "all" }}>{config?.twilio_whatsapp_number || twilioWhatsAppNumber || "—"}</code>
              {" · "}
              <strong>AiSensy business:</strong> <code style={{ userSelect: "all" }}>{config?.aisensy_whatsapp_number || aisensyWhatsappNumber || "—"}</code>
            </p>

            {/* ── Twilio WhatsApp ── */}
            <div
              style={{
                background: "var(--bg-base)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "1rem 1.15rem",
                marginBottom: "1.5rem",
              }}
            >
              <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.05rem", fontWeight: 700 }}>
                Twilio WhatsApp
              </h2>
              <p className="lead" style={{ margin: "0 0 0.75rem", fontSize: "0.88rem", color: "var(--text-secondary)" }}>
                Twilio delivers messages via the Twilio REST API — no QR code required. Configure the webhook URL in your Twilio console to start receiving messages.
              </p>

              {/* Sender number */}
              <div style={{ marginBottom: "0.85rem" }}>
                <p style={{ margin: "0 0 0.25rem", fontSize: "0.85rem", fontWeight: 600 }}>Sender number</p>
                <code style={{ fontSize: "0.9rem", userSelect: "all" }}>
                  {config?.twilio_whatsapp_number || twilioWhatsAppNumber || "(not set — configure in the Config tab)"}
                </code>
                <p style={{ margin: "0.3rem 0 0", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                  Update in the <strong>Config</strong> tab under <em>Twilio WhatsApp</em>.
                </p>
              </div>

              {/* Inbound webhook URL */}
              <div style={{ padding: "0.75rem", background: "var(--bg-muted, #f9fafb)", border: "1px solid var(--border)", borderRadius: "var(--radius-xs, 4px)" }}>
                <p style={{ margin: "0 0 0.4rem", fontSize: "0.83rem", fontWeight: 700 }}>
                  Twilio Console → Sandbox / Phone number settings
                </p>
                <p style={{ margin: "0 0 0.4rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Set <strong>When a message comes in</strong> to:
                </p>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <code style={{ fontSize: "0.8rem", wordBreak: "break-all", flex: 1 }}>
                    {TWILIO_INBOUND_WEBHOOK_URL}
                  </code>
                  <button
                    type="button"
                    style={{ flexShrink: 0, fontSize: "0.75rem", padding: "0.25rem 0.55rem" }}
                    onClick={() => {
                      void navigator.clipboard.writeText(TWILIO_INBOUND_WEBHOOK_URL);
                      toast.success("Webhook URL copied.");
                    }}
                  >
                    Copy
                  </button>
                </div>
                <p style={{ margin: "0.45rem 0 0", fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                  HTTP method: <strong>POST</strong>.
                  Sandbox: join the sandbox on{" "}
                  <a href="https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                    console.twilio.com
                  </a>{" "}
                  first. For a Business number, verify it and configure the webhook in your Twilio phone number's messaging settings.
                </p>
              </div>
            </div>

            {/* ── AiSensy quick reference ── */}
            <div
              style={{
                background: "var(--bg-base)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "1rem 1.15rem",
                marginBottom: "1.5rem",
              }}
            >
              <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.05rem", fontWeight: 700 }}>
                AiSensy
              </h2>
              <p className="lead" style={{ margin: "0 0 0.5rem", fontSize: "0.88rem", color: "var(--text-secondary)" }}>
                Configure project id and API key in the <strong>Config</strong> tab. Webhook (POST) for Meta / AiSensy:
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                <code style={{ fontSize: "0.8rem", wordBreak: "break-all", flex: 1 }}>{AISENSY_INBOUND_WEBHOOK_URL}</code>
                <button
                  type="button"
                  style={{ flexShrink: 0, fontSize: "0.75rem", padding: "0.25rem 0.55rem" }}
                  onClick={() => {
                    void navigator.clipboard.writeText(AISENSY_INBOUND_WEBHOOK_URL);
                    toast.success("AiSensy webhook URL copied.");
                  }}
                >
                  Copy
                </button>
              </div>
            </div>

            {/* ── Weaviate collection ── */}
            <div
              style={{
                background: "var(--bg-base)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "1rem 1.15rem",
                marginBottom: "1.5rem",
              }}
            >
              <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.05rem", fontWeight: 700 }}>
                Weaviate vector collection
              </h2>
              <p className="lead" style={{ margin: "0 0 0.75rem", fontSize: "0.88rem" }}>
                Collection name:{" "}
                <code style={{ userSelect: "all" }}>
                  {config?.weaviate_collection ?? portalOverview?.integration?.weaviate_collection ?? "—"}
                </code>
              </p>
              <p className="lead" style={{ margin: "0 0 0.75rem", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                Click <strong>Ensure collection</strong> to create the Weaviate collection if it is
                missing (safe to call even if it already exists). This also marks the readiness gate as
                satisfied. You need to do this before uploading documents if onboarding failed.
              </p>
              <p className="lead" style={{ margin: "0 0 0.75rem", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                To create manually in Weaviate, use class name above with properties:{" "}
                <code>document_id, company_id, chunk_index (int), chunk_text, file_name, s3_key</code>
                {" "}— all text unless noted.
              </p>
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                <button
                  type="button"
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const res = await weaviateEnsureCollection(accessToken, companyId);
                      setWeaviateResult(res);
                      toast.success(res.created ? "Collection created." : "Collection already existed.");
                      await loadAll();
                    })
                  }
                >
                  Ensure collection
                </button>
                {weaviateResult && (
                  <span
                    style={{
                      fontSize: "0.87rem",
                      padding: "0.3rem 0.65rem",
                      borderRadius: "var(--radius-sm)",
                      background: weaviateResult.created ? "var(--success-bg, #d1fae5)" : "var(--bg-raised)",
                      color: weaviateResult.created ? "var(--success, #065f46)" : "var(--text-secondary)",
                    }}
                  >
                    {weaviateResult.created
                      ? `✓ Created: ${weaviateResult.collection_name}`
                      : `Already existed: ${weaviateResult.collection_name}`}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Inbox (WhatsApp threads) ── */}
        {tab === "inbox" && (
          <div className="tab-panel">
            <p className="lead" style={{ margin: "0 0 0.6rem", fontSize: "0.9rem" }}>
              Customer WhatsApp threads for this company. Set <strong>lead</strong> (hot / warm / cold) and mark when the
              customer&apos;s inquiry is <strong>complete</strong> — the number stays visible for follow-up.
            </p>
            <CompanyInbox accessToken={accessToken} companyId={companyId} />
          </div>
        )}

        {/* ── Handoffs ── */}
        {tab === "handoffs" && (
          <div className="tab-panel">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
              <p className="lead" style={{ margin: 0 }}>
                {handoffs.length} handoff{handoffs.length !== 1 ? "s" : ""}
              </p>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => void run(async () => {
                  setHandoffs(await listCompanyHandoffs(accessToken, companyId));
                  toast.success("Handoffs refreshed.");
                })}
              >
                Refresh handoffs
              </button>
            </div>

            {handoffs.length === 0 && (
              <p className="lead" style={{ textAlign: "center", padding: "2rem" }}>No handoffs.</p>
            )}

            {handoffs.length > 0 && (
              <div className="table-scroll">
              <table className="companies">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Conversation</th>
                    <th>Assign agent</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {handoffs.map((h) => (
                    <tr key={h.id}>
                      <td>
                        <span className={`badge ${h.status === "open" ? "badge--draft" : h.status === "assigned" ? "badge--active" : "badge--inactive"}`}>
                          {h.status}
                        </span>
                      </td>
                      <td><code style={{ fontSize: "0.78rem" }}>{h.conversation_id.slice(0, 13)}…</code></td>
                      <td>
                        <input
                          type="text"
                          placeholder="agent_id"
                          style={{ width: "100%", minWidth: 120 }}
                          value={assignByHandoff[h.id] ?? ""}
                          onChange={(e) => setAssignByHandoff((prev) => ({ ...prev, [h.id]: e.target.value }))}
                        />
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            onClick={() => void run(async () => {
                              const aid = assignByHandoff[h.id]?.trim();
                              if (!aid) {
                                toast.error("Enter an agent ID to assign.");
                                return;
                              }
                              await assignHandoff(accessToken, h.id, aid);
                              toast.success("Assigned.");
                              setHandoffs(await listCompanyHandoffs(accessToken, companyId));
                            })}
                          >
                            Assign
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            onClick={() => void run(async () => {
                              await resolveHandoff(accessToken, h.id);
                              toast.success("Resolved.");
                              setHandoffs(await listCompanyHandoffs(accessToken, companyId));
                            })}
                          >
                            Resolve
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}

            <div style={{ background: "var(--bg-base)", borderRadius: "var(--radius-md)", padding: "1.25rem", border: "1px solid var(--border)", marginTop: "0.5rem" }}>
              <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 700 }}>Conversation actions</h3>
              <div className="grid-responsive">
                <div className="stack" style={{ gap: "0.5rem" }}>
                  <label>
                    <span>Request handoff for conversation</span>
                    <input
                      type="text"
                      value={convIdHandoff}
                      onChange={(e) => setConvIdHandoff(e.target.value)}
                      placeholder="conversation UUID"
                    />
                  </label>
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy || !convIdHandoff.trim()}
                    onClick={() => void run(async () => {
                      await requestConversationHandoff(accessToken, convIdHandoff.trim());
                      toast.success("Handoff created.");
                      setHandoffs(await listCompanyHandoffs(accessToken, companyId));
                    })}
                  >
                    Request handoff
                  </button>
                </div>
                <div className="stack" style={{ gap: "0.5rem" }}>
                  <label>
                    <span>Resume bot for conversation</span>
                    <input
                      type="text"
                      value={convIdResume}
                      onChange={(e) => setConvIdResume(e.target.value)}
                      placeholder="conversation UUID"
                    />
                  </label>
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy || !convIdResume.trim()}
                    onClick={() => void run(async () => {
                      await resumeConversationBot(accessToken, convIdResume.trim());
                      toast.success("Bot mode resumed.");
                    })}
                  >
                    Resume bot
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Analytics ── */}
        {tab === "analytics" && (
          <div className="tab-panel">
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
              <label className="support-inline" style={{ gap: "0.5rem" }}>
                <span className="support-period-label">Period:</span>
                <select
                  value={periodDays}
                  style={{ width: "auto" }}
                  onChange={(e) => setPeriodDays(Number(e.target.value))}
                >
                  <option value={7}>7 days</option>
                  <option value={30}>30 days</option>
                  <option value={90}>90 days</option>
                </select>
              </label>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => void loadAnalytics({ notifySuccess: true })}
              >
                Refresh analytics
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => {
                  const ts = new Date().toISOString().replaceAll(":", "-");
                  downloadXlsx(`analytics-${companyId}-${periodDays}d-${ts}.xlsx`, {
                    overview,
                    languages: analyticsLang,
                    leads: analyticsLeadsData,
                    fallbacks: analyticsFb,
                    handoffs: analyticsHo,
                    top_queries: analyticsTQ,
                    products: productAnalytics,
                  });
                  toast.success("Spreadsheet download started.");
                }}
              >
                Download XLSX
              </button>
            </div>

            {analyticsLoading && (
              <p className="analytics-updating-hint">
                <Spinner size="sm" label="Updating" />
                <span>Updating analytics…</span>
              </p>
            )}

            {/* Overview KPIs */}
            {overview && typeof overview === "object" ? (
              <div style={{ marginTop: "1rem" }}>
                <h3 className="support-subhead">Overview</h3>
                {(() => {
                  const o = overview as Record<string, unknown>;
                  const kpis = [
                    { label: "Customer msgs", value: n(o.total_customer_messages) },
                    { label: "Bot msgs", value: n(o.total_bot_messages) },
                    { label: "Fallbacks", value: n(o.total_fallback_messages) },
                    { label: "Handoffs", value: n(o.total_handoffs) },
                    { label: "Active convs", value: n(o.active_conversations) },
                    { label: "Fallback rate", value: `${(n(o.fallback_rate) * 100).toFixed(1)}%` },
                    { label: "Handoff rate", value: `${(n(o.handoff_rate) * 100).toFixed(1)}%` },
                  ];
                  return (
                    <div className="kpi-grid">
                      {kpis.map((k) => (
                        <div key={k.label} className="kpi-tile">
                          <div className="kpi-tile__label">{k.label}</div>
                          <div className="kpi-tile__value">{String(k.value)}</div>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
            ) : analyticsLoading ? (
              <div style={{ marginTop: "1rem" }}>
                <h3 className="support-subhead">Overview</h3>
                <div className="section-loader">
                  <Spinner size="md" label="Loading overview" />
                  <span>Loading overview…</span>
                </div>
              </div>
            ) : (
              <div style={{ marginTop: "1rem" }}>
                <h3 className="support-subhead">Overview</h3>
                <pre className="support-pre">{overview == null ? "— no data —" : jsonPrettyUi(overview)}</pre>
              </div>
            )}

            {/* Leads */}
            <div style={{ marginTop: "1rem" }}>
              <h3 className="support-subhead">Leads</h3>
              {analyticsLoading && !analyticsLeadsData ? (
                <div className="section-loader">
                  <Spinner size="md" label="Loading leads" />
                  <span>Loading leadsâ€¦</span>
                </div>
              ) : !analyticsLeadsData ? (
                <pre className="support-pre">â€” no data â€”</pre>
              ) : (
                (() => {
                  const totals = analyticsLeadsData.totals ?? { hot: 0, warm: 0, cold: 0 };
                  const totalLeads = n(totals.hot) + n(totals.warm) + n(totals.cold);
                  const rows = analyticsLeadsData.series.map((r) => ({
                    ...r,
                    label: new Date(`${r.date}T00:00:00`).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    }),
                  }));
                  return (
                    <div className="analytics-split">
                      <div className="chart-card chart-card--tall" style={{ height: 320 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={rows} margin={{ top: 8, right: 18, bottom: 0, left: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="label" minTickGap={18} />
                            <YAxis allowDecimals={false} />
                            <Tooltip />
                            <Legend />
                            <Line type="monotone" dataKey="hot" name="Hot" stroke="#dc2626" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                            <Line type="monotone" dataKey="warm" name="Warm" stroke="#d97706" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                            <Line type="monotone" dataKey="cold" name="Cold" stroke="#2563eb" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="table-scroll" style={{ border: "none", background: "var(--bg-base)" }}>
                        <table className="companies" style={{ fontSize: "0.86rem" }}>
                          <thead>
                            <tr><th>Lead type</th><th>Total</th><th>%</th></tr>
                          </thead>
                          <tbody>
                            {[
                              { label: "Hot", value: n(totals.hot), color: "#dc2626" },
                              { label: "Warm", value: n(totals.warm), color: "#d97706" },
                              { label: "Cold", value: n(totals.cold), color: "#2563eb" },
                            ].map((r) => (
                              <tr key={r.label}>
                                <td style={{ fontWeight: 600, color: r.color }}>{r.label}</td>
                                <td>{r.value}</td>
                                <td>{totalLeads > 0 ? ((r.value / totalLeads) * 100).toFixed(1) : "0.0"}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })()
              )}
            </div>

            {/* Languages */}
            <div style={{ marginTop: "1rem" }}>
              <h3 className="support-subhead">Languages</h3>
              {analyticsLang && typeof analyticsLang === "object" ? (
                (() => {
                  const a = analyticsLang as Record<string, unknown>;
                  const breakdown = Array.isArray(a.breakdown) ? (a.breakdown as Array<Record<string, unknown>>) : [];
                  const pieData = breakdown.map((b) => ({
                    name: String(b.language ?? "unknown"),
                    value: n(b.count),
                    pct: n(b.percentage),
                  }));
                  return (
                    <div className="analytics-split">
                      <div className="chart-card chart-card--tall" style={{ height: 260 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Tooltip />
                            <Legend />
                            <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={90} label>
                              {pieData.map((_, i) => (
                                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="table-scroll" style={{ border: "none", background: "var(--bg-base)" }}>
                        <table className="companies" style={{ fontSize: "0.86rem" }}>
                          <thead>
                            <tr><th>Language</th><th>Count</th><th>%</th></tr>
                          </thead>
                          <tbody>
                            {pieData.length === 0 ? (
                              <tr><td colSpan={3} style={{ color: "var(--text-secondary)" }}>—</td></tr>
                            ) : pieData.map((r) => (
                              <tr key={r.name}>
                                <td style={{ fontWeight: 600 }}>{r.name}</td>
                                <td>{r.value}</td>
                                <td>{r.pct.toFixed(1)}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })()
              ) : analyticsLoading ? (
                <div className="section-loader">
                  <Spinner size="md" label="Loading languages" />
                  <span>Loading languages…</span>
                </div>
              ) : (
                <pre className="support-pre">{analyticsLang == null ? "— no data —" : jsonPrettyUi(analyticsLang)}</pre>
              )}
            </div>

            {/* Fallbacks */}
            <div style={{ marginTop: "1rem" }}>
              <h3 className="support-subhead">Fallbacks</h3>
              {analyticsFb && typeof analyticsFb === "object" ? (
                (() => {
                  const f = analyticsFb as Record<string, unknown>;
                  const top = Array.isArray(f.top_fallback_queries) ? (f.top_fallback_queries as Array<Record<string, unknown>>) : [];
                  // repo returns list[dict], likely {query,count}. tolerate other keys.
                  const rows = top
                    .map((x) => ({
                      query: String((x.query ?? x.normalized_query ?? x.text ?? "unknown") as unknown),
                      count: n(x.count),
                    }))
                    .slice(0, 10);
                  return (
                    <div className="chart-card chart-card--tall" style={{ height: 280 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={rows} margin={{ left: 10, right: 10 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="query" hide />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" fill="#ef4444" />
                        </BarChart>
                      </ResponsiveContainer>
                      <p className="lead" style={{ margin: "0.5rem 0 0", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                        Showing top fallback-triggering queries (top 10).
                      </p>
                    </div>
                  );
                })()
              ) : analyticsLoading ? (
                <div className="section-loader">
                  <Spinner size="md" label="Loading fallbacks" />
                  <span>Loading fallbacks…</span>
                </div>
              ) : (
                <pre className="support-pre">{analyticsFb == null ? "— no data —" : jsonPrettyUi(analyticsFb)}</pre>
              )}
            </div>

            {/* Handoffs */}
            <div style={{ marginTop: "1rem" }}>
              <h3 className="support-subhead">Handoffs</h3>
              {analyticsHo && typeof analyticsHo === "object" ? (
                (() => {
                  const h = analyticsHo as Record<string, unknown>;
                  const data = [
                    { name: "Pending", value: n(h.pending_count) },
                    { name: "Resolved", value: n(h.resolved_count) },
                    { name: "Cancelled", value: n(h.cancelled_count) },
                  ];
                  return (
                    <div className="chart-card" style={{ height: 240 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="value" fill="#2563eb" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  );
                })()
              ) : analyticsLoading ? (
                <div className="section-loader">
                  <Spinner size="md" label="Loading handoffs" />
                  <span>Loading handoffs…</span>
                </div>
              ) : (
                <pre className="support-pre">{analyticsHo == null ? "— no data —" : jsonPrettyUi(analyticsHo)}</pre>
              )}
            </div>

            {/* Top queries */}
            <div style={{ marginTop: "1rem" }}>
              <h3 className="support-subhead">Top queries</h3>
              {analyticsTQ && typeof analyticsTQ === "object" ? (
                (() => {
                  const t = analyticsTQ as Record<string, unknown>;
                  const top = Array.isArray(t.top_queries) ? (t.top_queries as Array<Record<string, unknown>>) : [];
                  const rows = top.slice(0, 10).map((x) => ({
                    query: String(x.query ?? "unknown"),
                    count: n(x.count),
                  }));
                  return (
                    <div className="chart-card chart-card--tall" style={{ height: 280 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={rows}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="query" hide />
                          <YAxis allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="count" fill="#10b981" />
                        </BarChart>
                      </ResponsiveContainer>
                      <p className="lead" style={{ margin: "0.5rem 0 0", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                        Showing top customer queries (top 10).
                      </p>
                    </div>
                  );
                })()
              ) : analyticsLoading ? (
                <div className="section-loader">
                  <Spinner size="md" label="Loading top queries" />
                  <span>Loading top queries…</span>
                </div>
              ) : (
                <pre className="support-pre">{analyticsTQ == null ? "— no data —" : jsonPrettyUi(analyticsTQ)}</pre>
              )}
            </div>

            {/* Product analytics */}
            <div>
              <h3 className="support-subhead">Products — RAG interactions</h3>
              {analyticsLoading && !productAnalytics ? (
                <div className="section-loader" style={{ marginTop: "0.5rem" }}>
                  <Spinner size="md" label="Loading product analytics" />
                  <span>Loading product analytics…</span>
                </div>
              ) : !productAnalytics || productAnalytics.total_events === 0 ? (
                <p className="lead" style={{ fontSize: "0.88rem" }}>
                  No product events yet. Products must be indexed and queried via RAG to appear here.
                </p>
              ) : (
                (() => {
                  const chartRows = productAnalytics.series.map((point) => ({
                    date: point.date,
                    inquired: point.retrieved_count,
                    suggested: point.suggested_count,
                  }));
                  return (
                    <div className="stack" style={{ gap: "1rem" }}>
                      <div className="chart-card chart-card--tall" style={{ height: 340 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={chartRows} margin={{ top: 10, right: 18, bottom: 12, left: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="date" minTickGap={18} />
                            <YAxis allowDecimals={false} />
                            <Tooltip />
                            <Legend />
                            <Line type="monotone" dataKey="inquired" name="Customer inquired" stroke="#2563eb" strokeWidth={2.4} dot={false} />
                            <Line type="monotone" dataKey="suggested" name="Bot suggested" stroke="#10b981" strokeWidth={2.4} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="grid-responsive" style={{ gap: "1rem" }}>
                        <div>
                          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem", fontWeight: 600 }}>
                            Most asked about (retrieved)
                          </h4>
                          <div className="table-scroll">
                          <table className="companies" style={{ fontSize: "0.82rem" }}>
                            <thead>
                              <tr><th>Product</th><th>Retrieved</th><th>Convs</th></tr>
                            </thead>
                            <tbody>
                              {productAnalytics.top_retrieved.slice(0, 10).map((item) => (
                                <tr key={item.product_id}>
                                  <td>{item.name}{item.sku ? <span style={{ color: "var(--text-secondary)", marginLeft: "0.35rem" }}>({item.sku})</span> : null}</td>
                                  <td style={{ fontWeight: 600 }}>{item.retrieved_count}</td>
                                  <td>{item.unique_conversations}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          </div>
                        </div>
                        <div>
                          <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem", fontWeight: 600 }}>
                            Most suggested by bot
                          </h4>
                          <div className="table-scroll">
                          <table className="companies" style={{ fontSize: "0.82rem" }}>
                            <thead>
                              <tr><th>Product</th><th>Suggested</th></tr>
                            </thead>
                            <tbody>
                              {productAnalytics.top_suggested.slice(0, 10).map((item) => (
                                <tr key={item.product_id}>
                                  <td>{item.name}</td>
                                  <td style={{ fontWeight: 600 }}>{item.suggested_count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()
              )}
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
