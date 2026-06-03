import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import * as XLSX from "xlsx";
import {
  campaignAction,
  listCampaigns,
  quickSendCampaign,
  type QuickSendRow,
  type WhatsAppCampaign,
} from "../lib/supportApi";
import { PageLoader, Spinner } from "../components/Spinner";
import { useToast } from "../context/ToastContext";

type Props = {
  accessToken: string;
  companyId: string;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}

function statusColor(s: string): string {
  switch (s) {
    case "running": return "#22c55e";
    case "completed": return "#3b82f6";
    case "pending_template": return "#f59e0b";
    case "paused": return "#6b7280";
    case "cancelled":
    case "template_rejected": return "#ef4444";
    default: return "#a78bfa";
  }
}

function statusLabel(s: string): string {
  switch (s) {
    case "pending_template": return "Awaiting Template Approval";
    case "template_rejected": return "Template Rejected";
    case "running": return "Running";
    case "completed": return "Completed";
    case "paused": return "Paused";
    case "cancelled": return "Cancelled";
    case "draft": return "Draft";
    default: return s;
  }
}

function fmt(n: number): string {
  return n.toLocaleString();
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "2-digit", month: "short", year: "numeric",
  });
}

// ── Parse uploaded file ───────────────────────────────────────────────────────

function parseUploadedFile(file: File): Promise<{ rows: Record<string, string>[]; columns: string[] }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target!.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array" });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json<Record<string, string>>(ws, { defval: "" });
        const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
        resolve({ rows: rows as Record<string, string>[], columns });
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = () => reject(new Error("File read failed."));
    reader.readAsArrayBuffer(file);
  });
}

function parsePhoneText(text: string): QuickSendRow[] {
  return text
    .split(/[\n,;]+/)
    .map((l) => l.trim().replace(/\D/g, ""))
    .filter((l) => l.length >= 10)
    .map((phone) => ({ phone }));
}

// ── New Campaign Modal ────────────────────────────────────────────────────────

type WizardStep = "compose" | "recipients" | "preview";

type ModalProps = {
  accessToken: string;
  companyId: string;
  onClose: () => void;
  onCreated: () => void;
};

function NewCampaignModal({ accessToken, companyId, onClose, onCreated }: ModalProps) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<WizardStep>("compose");
  const [busy, setBusy] = useState(false);

  // Step 1 — compose
  const [campaignName, setCampaignName] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [templateNameTouched, setTemplateNameTouched] = useState(false);
  const [messageBody, setMessageBody] = useState("");
  const [headerText, setHeaderText] = useState("");
  const [footerText, setFooterText] = useState("");
  const [language, setLanguage] = useState("en");
  const [category, setCategory] = useState<"marketing" | "utility">("marketing");

  // Step 2 — recipients
  const [inputMode, setInputMode] = useState<"upload" | "paste">("upload");
  const [rows, setRows] = useState<QuickSendRow[]>([]);
  const [phoneColumn, setPhoneColumn] = useState("phone");
  const [columns, setColumns] = useState<string[]>([]);
  const [pasteText, setPasteText] = useState("");
  const [fileName, setFileName] = useState("");

  // sync template name from campaign name
  useEffect(() => {
    if (!templateNameTouched && campaignName) {
      setTemplateName(slugify(campaignName));
    }
  }, [campaignName, templateNameTouched]);

  const handleFile = async (file: File) => {
    try {
      const parsed = await parseUploadedFile(file);
      setRows(parsed.rows as QuickSendRow[]);
      setColumns(parsed.columns);
      setFileName(file.name);
      const phoneCol = parsed.columns.find((c) =>
        ["phone", "phone_number", "mobile", "whatsapp", "number"].includes(c.toLowerCase()),
      );
      setPhoneColumn(phoneCol ?? parsed.columns[0] ?? "phone");
    } catch {
      toast.error("Could not read file. Use .xlsx or .csv.");
    }
  };

  const handleFilePick = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await handleFile(file);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) await handleFile(file);
  };

  const recipientCount =
    inputMode === "upload"
      ? rows.length
      : parsePhoneText(pasteText).length;

  const finalRows: QuickSendRow[] =
    inputMode === "upload" ? rows : parsePhoneText(pasteText);

  const canNextCompose = campaignName.trim() && templateName.trim() && messageBody.trim();
  const canNextRecipients = recipientCount > 0;

  const handleSend = async () => {
    setBusy(true);
    try {
      const result = await quickSendCampaign(accessToken, companyId, {
        campaign_name: campaignName.trim(),
        template_name: templateName.trim(),
        template_body: messageBody.trim(),
        template_header: headerText.trim() || undefined,
        template_footer: footerText.trim() || undefined,
        language_code: language,
        category,
        phone_column: inputMode === "upload" ? phoneColumn : "phone",
        rows: finalRows,
      });
      if (result.template_status === "APPROVED") {
        toast.success(`Campaign started! ${fmt(finalRows.length)} messages queued.`);
      } else {
        toast.success("Template submitted for Meta review. Campaign will auto-start once approved.");
      }
      onCreated();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create campaign.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-box"
        style={{ maxWidth: 620, width: "100%" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: "1.2rem" }}>New Bulk Campaign</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Step tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: "1px solid var(--border)" }}>
          {(["compose", "recipients", "preview"] as WizardStep[]).map((s, i) => (
            <button
              key={s}
              className="tab-btn"
                style={{
                fontWeight: step === s ? 700 : 400,
                borderBottom: step === s ? "2px solid var(--accent)" : "2px solid transparent",
                color: step === s ? "var(--accent)" : "var(--text-muted)",
                padding: "6px 14px",
                background: "none",
                border: "none",
                cursor: i === 0 || (i === 1 && canNextCompose) || (i === 2 && canNextCompose && canNextRecipients) ? "pointer" : "not-allowed",
                opacity: i === 0 || (i === 1 && canNextCompose) || (i === 2 && canNextCompose && canNextRecipients) ? 1 : 0.4,
              }}
              onClick={() => {
                if (i === 0) setStep("compose");
                if (i === 1 && canNextCompose) setStep("recipients");
                if (i === 2 && canNextCompose && canNextRecipients) setStep("preview");
              }}
            >
              {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {/* ── Step 1: Compose ── */}
        {step === "compose" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <label className="form-label">
              Campaign Name
              <input
                className="form-input"
                placeholder="e.g. May Offer Blast"
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                autoFocus
              />
            </label>

            <label className="form-label">
              Template Name <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>(lowercase, underscores only — unique per message)</span>
              <input
                className="form-input"
                placeholder="e.g. may_offer_blast"
                value={templateName}
                onChange={(e) => { setTemplateName(slugify(e.target.value)); setTemplateNameTouched(true); }}
              />
            </label>

            <label className="form-label">
              Message Body <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>({messageBody.length}/1024)</span>
              <textarea
                className="form-input"
                rows={5}
                placeholder="Namaste! SKinRange ki taraf se special offer..."
                value={messageBody}
                onChange={(e) => setMessageBody(e.target.value.slice(0, 1024))}
                style={{ resize: "vertical", fontFamily: "inherit" }}
              />
            </label>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <label className="form-label">
                Header Text <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>(optional)</span>
                <input className="form-input" placeholder="e.g. Special Offer" value={headerText} onChange={(e) => setHeaderText(e.target.value.slice(0, 60))} />
              </label>
              <label className="form-label">
                Footer Text <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>(optional)</span>
                <input className="form-input" placeholder="e.g. Reply STOP to unsubscribe" value={footerText} onChange={(e) => setFooterText(e.target.value.slice(0, 60))} />
              </label>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <label className="form-label">
                Language
                <select className="form-input" value={language} onChange={(e) => setLanguage(e.target.value)}>
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="en_US">English (US)</option>
                </select>
              </label>
              <label className="form-label">
                Category
                <select className="form-input" value={category} onChange={(e) => setCategory(e.target.value as "marketing" | "utility")}>
                  <option value="marketing">Marketing</option>
                  <option value="utility">Utility</option>
                </select>
              </label>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
              <button className="btn-primary" disabled={!canNextCompose} onClick={() => setStep("recipients")}>
                Next: Recipients →
              </button>
            </div>
          </div>
        )}

        {/* ── Step 2: Recipients ── */}
        {step === "recipients" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className={inputMode === "upload" ? "btn-primary" : "btn-secondary"}
                style={{ fontSize: "0.85rem", padding: "6px 16px" }}
                onClick={() => setInputMode("upload")}
              >
                Upload File
              </button>
              <button
                className={inputMode === "paste" ? "btn-primary" : "btn-secondary"}
                style={{ fontSize: "0.85rem", padding: "6px 16px" }}
                onClick={() => setInputMode("paste")}
              >
                Paste Numbers
              </button>
            </div>

            {inputMode === "upload" && (
              <>
                <div
                  style={{
                    border: "2px dashed var(--border)",
                    borderRadius: 10,
                    padding: "32px 24px",
                    textAlign: "center",
                    cursor: "pointer",
                    color: "var(--text-muted)",
                    transition: "border-color 0.2s",
                  }}
                  onClick={() => fileRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                >
                  <div style={{ fontSize: "2rem", marginBottom: 8 }}>📂</div>
                  {fileName
                    ? <><strong>{fileName}</strong><br /><span style={{ fontSize: "0.85rem" }}>{fmt(rows.length)} rows loaded</span></>
                    : <><strong>Drop your Excel or CSV file here</strong><br /><span style={{ fontSize: "0.85rem" }}>or click to browse</span></>}
                  <input ref={fileRef} type="file" accept=".xlsx,.csv,.xls" style={{ display: "none" }} onChange={handleFilePick} />
                </div>

                {columns.length > 0 && (
                  <label className="form-label">
                    Phone Column
                    <select className="form-input" value={phoneColumn} onChange={(e) => setPhoneColumn(e.target.value)}>
                      {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </label>
                )}

                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Phone numbers must be in international format without +, e.g. <code>919876543210</code>
                </div>
              </>
            )}

            {inputMode === "paste" && (
              <>
                <label className="form-label">
                  Paste Phone Numbers <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>(one per line, or comma-separated)</span>
                  <textarea
                    className="form-input"
                    rows={8}
                    placeholder={"919876543210\n918765432109\n916371688288"}
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    style={{ resize: "vertical", fontFamily: "monospace", fontSize: "0.9rem" }}
                  />
                </label>
                {pasteText && (
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    {fmt(recipientCount)} valid numbers detected
                  </div>
                )}
              </>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              <button className="btn-secondary" onClick={() => setStep("compose")}>← Back</button>
              <button className="btn-primary" disabled={!canNextRecipients} onClick={() => setStep("preview")}>
                Preview & Send →
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Preview & Send ── */}
        {step === "preview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ background: "var(--surface-2)", borderRadius: 10, padding: "16px 20px", display: "flex", flexDirection: "column", gap: 8, fontSize: "0.92rem" }}>
              <PreviewRow label="Campaign" value={campaignName} />
              <PreviewRow label="Template" value={templateName} />
              <PreviewRow label="Language" value={language} />
              <PreviewRow label="Category" value={category} />
              <PreviewRow label="Recipients" value={`${fmt(recipientCount)} numbers`} />
            </div>

            <div style={{ background: "var(--surface-2)", borderRadius: 10, padding: "14px 18px" }}>
              <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: 6 }}>MESSAGE PREVIEW</div>
              {headerText && <div style={{ fontWeight: 700, marginBottom: 4 }}>{headerText}</div>}
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{messageBody}</div>
              {footerText && <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: 6 }}>{footerText}</div>}
            </div>

            <div style={{
              background: "var(--warning-soft, #fef9c3)",
              color: "var(--warning-text, #713f12)",
              borderRadius: 8,
              padding: "10px 14px",
              fontSize: "0.83rem",
              lineHeight: 1.5,
            }}>
              ⏳ <strong>Meta Template Review:</strong> If this is a new template, Meta will review it (usually minutes to a few hours). The campaign will <strong>auto-start</strong> once approved — no action needed.
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              <button className="btn-secondary" onClick={() => setStep("recipients")}>← Back</button>
              <button className="btn-primary" disabled={busy} onClick={handleSend}>
                {busy ? <Spinner size={16} /> : "🚀 Send Campaign"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: 12 }}>
      <span style={{ color: "var(--text-muted)", minWidth: 100 }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ── Campaign Card ─────────────────────────────────────────────────────────────

function CampaignCard({ campaign, token, companyId, onRefresh }: {
  campaign: WhatsAppCampaign;
  token: string;
  companyId: string;
  onRefresh: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const doAction = async (action: "start" | "pause" | "cancel" | "retry_failed") => {
    setBusy(true);
    try {
      await campaignAction(token, companyId, campaign.id, action);
      toast.success(`Campaign ${action}ed.`);
      onRefresh();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  const s = campaign.status;
  const total = campaign.total_recipients || 1;
  const sentPct = Math.round((campaign.sent_count / total) * 100);

  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      padding: "18px 20px",
      display: "flex",
      flexDirection: "column",
      gap: 10,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: "1rem" }}>{campaign.name}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2 }}>
            Template: <code style={{ fontSize: "0.78rem" }}>{campaign.template_name}</code>
            &ensp;·&ensp;Created {fmtDate(campaign.created_at)}
          </div>
        </div>
        <span style={{
          display: "inline-block",
          padding: "3px 10px",
          borderRadius: 999,
          fontSize: "0.75rem",
          fontWeight: 600,
          background: statusColor(s) + "22",
          color: statusColor(s),
          whiteSpace: "nowrap",
        }}>
          {statusLabel(s)}
        </span>
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 20, fontSize: "0.85rem", color: "var(--text-muted)", flexWrap: "wrap" }}>
        <span>📋 {fmt(campaign.total_recipients)} recipients</span>
        <span>✅ {fmt(campaign.sent_count)} sent</span>
        <span>❌ {fmt(campaign.failed_count)} failed</span>
        <span>⏭ {fmt(campaign.skipped_count)} skipped</span>
      </div>

      {/* Progress bar */}
      {s === "running" && (
        <div style={{ height: 6, borderRadius: 4, background: "var(--border)", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${sentPct}%`, background: "#22c55e", borderRadius: 4, transition: "width 0.5s" }} />
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
        {s === "draft" && <button className="btn-primary" style={{ fontSize: "0.82rem", padding: "4px 14px" }} disabled={busy} onClick={() => doAction("start")}>▶ Start</button>}
        {s === "running" && <button className="btn-secondary" style={{ fontSize: "0.82rem", padding: "4px 14px" }} disabled={busy} onClick={() => doAction("pause")}>⏸ Pause</button>}
        {s === "paused" && <button className="btn-primary" style={{ fontSize: "0.82rem", padding: "4px 14px" }} disabled={busy} onClick={() => doAction("start")}>▶ Resume</button>}
        {(s === "running" || s === "paused" || s === "pending_template") && (
          <button className="btn-danger" style={{ fontSize: "0.82rem", padding: "4px 14px" }} disabled={busy} onClick={() => doAction("cancel")}>✕ Cancel</button>
        )}
        {campaign.failed_count > 0 && (
          <button className="btn-secondary" style={{ fontSize: "0.82rem", padding: "4px 14px" }} disabled={busy} onClick={() => doAction("retry_failed")}>↻ Retry Failed</button>
        )}
        {busy && <Spinner size={16} />}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function CompanyCampaigns({ accessToken, companyId }: Props) {
  const toast = useToast();
  const [campaigns, setCampaigns] = useState<WhatsAppCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await listCampaigns(accessToken, companyId);
      setCampaigns(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load campaigns.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, companyId, toast]);

  useEffect(() => {
    void load();
    // Auto-refresh every 30s (to pick up pending_template → running transitions)
    timerRef.current = setInterval(() => { void load(); }, 30_000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [load]);

  const hasPending = campaigns.some((c) => c.status === "pending_template" || c.status === "running");

  if (loading) return <PageLoader message="Loading campaigns…" />;

  return (
    <div style={{ maxWidth: 820, margin: "0 auto", padding: "24px 16px" }}>
      {/* Page header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "1.5rem" }}>Campaign Manager</h1>
          <p style={{ margin: "4px 0 0", color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Send bulk WhatsApp messages to your customers.
            {hasPending && " · Auto-refreshing every 30s"}
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          + New Campaign
        </button>
      </div>

      {/* Campaign list */}
      {campaigns.length === 0 ? (
        <div style={{
          textAlign: "center",
          padding: "60px 20px",
          color: "var(--text-muted)",
          border: "2px dashed var(--border)",
          borderRadius: 14,
        }}>
          <div style={{ fontSize: "3rem", marginBottom: 12 }}>📣</div>
          <div style={{ fontWeight: 600, fontSize: "1.1rem", marginBottom: 6 }}>No campaigns yet</div>
          <div style={{ fontSize: "0.9rem", marginBottom: 20 }}>Send your first bulk WhatsApp message in seconds.</div>
          <button className="btn-primary" onClick={() => setShowModal(true)}>+ New Campaign</button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {campaigns.map((c) => (
            <CampaignCard
              key={c.id}
              campaign={c}
              token={accessToken}
              companyId={companyId}
              onRefresh={load}
            />
          ))}
        </div>
      )}

      {showModal && (
        <NewCampaignModal
          accessToken={accessToken}
          companyId={companyId}
          onClose={() => setShowModal(false)}
          onCreated={() => { setShowModal(false); void load(); }}
        />
      )}
    </div>
  );
}
