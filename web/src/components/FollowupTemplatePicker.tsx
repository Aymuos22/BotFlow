import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createMetaWhatsAppTemplate,
  listMetaWhatsAppTemplates,
  type MetaWhatsAppTemplate,
} from "../lib/supportApi";
import { useToast } from "../context/ToastContext";

function normalizeMetaTemplateLanguage(
  raw: MetaWhatsAppTemplate["language"],
): string {
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  if (raw && typeof raw === "object" && "code" in raw) {
    const c = (raw as { code?: unknown }).code;
    if (typeof c === "string" && c.trim()) return c.trim();
  }
  return "en";
}

function templateRowKey(t: MetaWhatsAppTemplate): string {
  return `${t.name}\x1f${normalizeMetaTemplateLanguage(t.language)}`;
}

/** Readable preview from Meta template components (BODY / HEADER TEXT / FOOTER). */
export function metaTemplatePreviewText(t: MetaWhatsAppTemplate): string {
  const comps = t.components ?? [];
  const parts: string[] = [];
  for (const raw of comps) {
    const c = raw as Record<string, unknown>;
    const typ = String(c.type ?? "").toUpperCase();
    if (typ === "HEADER") {
      const format = String(c.format ?? "").toUpperCase();
      if (format === "TEXT") {
        const text = String(c.text ?? "").trim();
        if (text) parts.push(`[Header]\n${text}`);
      } else if (format) {
        parts.push(`[Header: ${format.toLowerCase()} media]`);
      }
    }
    if (typ === "BODY") {
      const text = String(c.text ?? "").trim();
      if (text) parts.push(text);
    }
    if (typ === "FOOTER") {
      const text = String(c.text ?? "").trim();
      if (text) parts.push(`[Footer]\n${text}`);
    }
  }
  return (
    parts.join("\n\n") ||
    "(Meta returned no body/header text — open WhatsApp Manager to inspect this template.)"
  );
}

const META_MANAGER_URL =
  "https://business.facebook.com/latest/whatsapp_manager/message_templates";

/** Count contiguous positional placeholders {{1}}…{{n}} in body; -1 if invalid. */
function countBodyPlaceholders(body: string): number {
  const nums = new Set<number>();
  const re = /\{\{(\d+)\}\}/g;
  let m: RegExpExecArray | null = re.exec(body);
  while (m !== null) {
    nums.add(Number(m[1]));
    m = re.exec(body);
  }
  const sorted = [...nums].sort((a, b) => a - b);
  if (sorted.length === 0) return 0;
  for (let i = 0; i < sorted.length; i += 1) {
    if (sorted[i] !== i + 1) return -1;
  }
  return sorted.length;
}

/** Split comma-separated template variables (quotes optional). */
export function parseFollowupBodyVariablesCsv(csv: string): string[] {
  return csv
    .split(",")
    .map((s) => {
      let x = s.trim();
      if (
        (x.startsWith('"') && x.endsWith('"')) ||
        (x.startsWith("'") && x.endsWith("'"))
      ) {
        x = x.slice(1, -1).trim();
      }
      return x;
    })
    .filter(Boolean);
}

type Props = {
  accessToken: string;
  companyId: string;
  templateName: string;
  setTemplateName: (v: string) => void;
  languageCode: string;
  setLanguageCode: (v: string) => void;
  bodyVariablesCsv: string;
  setBodyVariablesCsv: (v: string) => void;
};

export default function FollowupTemplatePicker({
  accessToken,
  companyId,
  templateName,
  setTemplateName,
  languageCode,
  setLanguageCode,
  bodyVariablesCsv,
  setBodyVariablesCsv,
}: Props) {
  const toast = useToast();
  const [templates, setTemplates] = useState<MetaWhatsAppTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pickedKey, setPickedKey] = useState("");
  const [composerBusy, setComposerBusy] = useState(false);
  const [cName, setCName] = useState("");
  const [cCategory, setCCategory] = useState<"utility" | "marketing">("utility");
  const [cLang, setCLang] = useState("en_US");
  const [cHeader, setCHeader] = useState("");
  const [cBody, setCBody] = useState("");
  const [cFooter, setCFooter] = useState("");
  const [cExamples, setCExamples] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await listMetaWhatsAppTemplates(accessToken, companyId);
      setTemplates(rows);
    } catch (e) {
      setTemplates([]);
      setErr(e instanceof Error ? e.message : "Could not load Meta templates.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, companyId]);

  useEffect(() => {
    void load();
  }, [load]);

  const approved = useMemo(
    () =>
      templates.filter(
        (t) => (t.status ?? "").toUpperCase() === "APPROVED",
      ),
    [templates],
  );

  const previewTemplate = useMemo(() => {
    if (!pickedKey) return null;
    return templates.find((t) => templateRowKey(t) === pickedKey) ?? null;
  }, [pickedKey, templates]);

  const composerPlaceholderCount = useMemo(() => countBodyPlaceholders(cBody), [cBody]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
        <button type="button" className="secondary" disabled={loading} onClick={() => void load()}>
          {loading ? "Loading templates…" : "Refresh templates from Meta"}
        </button>
        {approved.length > 0 ? (
          <label style={{ flex: "1 1 220px", margin: 0 }}>
            <span>Pick approved template</span>
            <select
              value={pickedKey}
              onChange={(e) => {
                const key = e.target.value;
                setPickedKey(key);
                const row = templates.find((t) => templateRowKey(t) === key);
                if (row) {
                  setTemplateName(row.name);
                  setLanguageCode(normalizeMetaTemplateLanguage(row.language));
                }
              }}
            >
              <option value="">— Manual entry below —</option>
              {approved.map((t) => (
                <option key={templateRowKey(t)} value={templateRowKey(t)}>
                  {t.name} ({normalizeMetaTemplateLanguage(t.language)}) ·{" "}
                  {t.category ?? "?"}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      {err ? (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--danger, #b91c1c)" }}>
          {err}{" "}
          <span style={{ color: "var(--text-muted)" }}>
            Set Meta WhatsApp (phone_number_id + Graph token). Templates resolve your Business Account automatically.
          </span>
        </p>
      ) : null}

      <details className="support-card compact" style={{ marginTop: "0.15rem" }}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>
          Compose &amp; submit template to Meta (edit wording here)
        </summary>
        <p style={{ margin: "0.65rem 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
          Builds a new <strong>TEXT</strong> template (optional header/footer). Meta reviews submissions — wait for{" "}
          <strong>APPROVED</strong> before using it outside the ~24h session window. Changing copy later means submitting again
          (or editing in{" "}
          <a href={META_MANAGER_URL} target="_blank" rel="noopener noreferrer">
            WhatsApp Manager
          </a>
          ).
        </p>
        <div style={{ display: "grid", gap: "0.65rem" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.65rem" }}>
            <label style={{ margin: 0 }}>
              <span>New template name</span>
              <input
                value={cName}
                onChange={(e) => setCName(e.target.value)}
                placeholder="lead_followup_v3"
              />
            </label>
            <label style={{ margin: 0 }}>
              <span>Category</span>
              <select
                value={cCategory}
                onChange={(e) => setCCategory(e.target.value as "utility" | "marketing")}
              >
                <option value="utility">utility</option>
                <option value="marketing">marketing</option>
              </select>
            </label>
          </div>
          <label style={{ margin: 0 }}>
            <span>Language code</span>
            <input value={cLang} onChange={(e) => setCLang(e.target.value)} placeholder="en_US" />
          </label>
          <label style={{ margin: 0 }}>
            <span>Header (optional, plain text)</span>
            <input value={cHeader} onChange={(e) => setCHeader(e.target.value)} placeholder="Short headline" />
          </label>
          <label style={{ margin: 0 }}>
            <span>Body</span>
            <textarea
              rows={4}
              value={cBody}
              onChange={(e) => setCBody(e.target.value)}
              placeholder={'Hi {{1}}, still interested? Reply STOP to opt out.'}
              style={{ width: "100%", resize: "vertical" }}
            />
          </label>
          <label style={{ margin: 0 }}>
            <span>Footer (optional)</span>
            <input value={cFooter} onChange={(e) => setCFooter(e.target.value)} placeholder="Company · Hours" />
          </label>
          {composerPlaceholderCount === -1 ? (
            <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--danger, #b91c1c)" }}>
              Use contiguous placeholders only: {"{{1}}"}, {"{{2}}"}, … with no gaps.
            </p>
          ) : composerPlaceholderCount > 0 ? (
            <label style={{ margin: 0 }}>
              <span>{`Example values for {{1}}…{{${composerPlaceholderCount}}} (comma-separated)`}</span>
              <input
                value={cExamples}
                onChange={(e) => setCExamples(e.target.value)}
                placeholder='e.g. "Alex"'
              />
            </label>
          ) : null}
          <button
            type="button"
            className="primary"
            disabled={
              composerBusy ||
              !cName.trim() ||
              !cBody.trim() ||
              composerPlaceholderCount < 0 ||
              (composerPlaceholderCount > 0 &&
                parseFollowupBodyVariablesCsv(cExamples).length !== composerPlaceholderCount)
            }
            onClick={() => {
              void (async () => {
                const examples = parseFollowupBodyVariablesCsv(cExamples);
                if (composerPlaceholderCount > 0 && examples.length !== composerPlaceholderCount) {
                  toast.error(`Provide exactly ${composerPlaceholderCount} example value(s).`);
                  return;
                }
                setComposerBusy(true);
                try {
                  await createMetaWhatsAppTemplate(accessToken, companyId, {
                    name: cName.trim(),
                    category: cCategory,
                    language: cLang.trim(),
                    body_text: cBody.trim(),
                    header_text: cHeader.trim() || null,
                    footer_text: cFooter.trim() || null,
                    body_example_values: examples,
                  });
                  toast.success(
                    "Submitted to Meta. Finish approval in WhatsApp Manager, then refresh the template list.",
                  );
                  const slug = cName.trim().toLowerCase();
                  setTemplateName(slug);
                  setLanguageCode(cLang.trim());
                  setPickedKey("");
                  await load();
                  setCName("");
                  setCBody("");
                  setCFooter("");
                  setCHeader("");
                  setCExamples("");
                } catch (e) {
                  toast.error(e instanceof Error ? e.message : "Submit failed");
                } finally {
                  setComposerBusy(false);
                }
              })();
            }}
          >
            {composerBusy ? "Submitting…" : "Submit template to Meta"}
          </button>
        </div>
      </details>

      {!loading && templates.length === 0 && !err ? (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
          No templates returned yet — submit one above or check Meta credentials / permissions.
        </p>
      ) : null}

      {!loading && templates.length > 0 && approved.length === 0 ? (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
          Meta returned templates but none are <strong>APPROVED</strong> yet — finish review in WhatsApp Manager.
        </p>
      ) : null}

      <label>
        <span>Meta template name (sent outside the ~24h session window)</span>
        <input
          value={templateName}
          onChange={(e) => {
            setTemplateName(e.target.value);
            setPickedKey("");
          }}
          placeholder="follow_up_template"
        />
      </label>

      <label>
        <span>Language code (must match Meta, e.g. en_US)</span>
        <input
          value={languageCode}
          onChange={(e) => {
            setLanguageCode(e.target.value);
            setPickedKey("");
          }}
          placeholder="en or en_US"
        />
      </label>

      <label>
        <span>Template body variables (optional, comma-separated for {"{{1}}"}, {"{{2}}"}, …)</span>
        <input
          value={bodyVariablesCsv}
          onChange={(e) => setBodyVariablesCsv(e.target.value)}
          placeholder='e.g. "Rajesh","order #4521"'
        />
      </label>

      <div className="support-card compact" style={{ marginTop: "0.25rem" }}>
        <strong style={{ fontSize: "0.82rem" }}>Preview from Meta (read-only)</strong>
        <pre
          className="support-pre"
          style={{
            marginTop: "0.45rem",
            marginBottom: 0,
            maxHeight: 220,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontSize: "0.82rem",
          }}
        >
          {previewTemplate
            ? metaTemplatePreviewText(previewTemplate)
            : "Choose a template above or enter a name — preview appears when a synced template is selected."}
        </pre>
        <p style={{ margin: "0.55rem 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>
          Approved templates shown above are read-only snapshots from Meta. Use{" "}
          <strong>Compose &amp; submit template to Meta</strong> to draft new wording from here, or manage submissions in{" "}
          <a href={META_MANAGER_URL} target="_blank" rel="noopener noreferrer">
            WhatsApp Manager
          </a>
          . After Meta approves, press <strong>Refresh templates from Meta</strong>.
        </p>
      </div>
    </div>
  );
}
