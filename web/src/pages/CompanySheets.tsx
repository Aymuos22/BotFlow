import { useCallback, useEffect, useMemo, useState } from "react";
import { PageLoader, Spinner } from "../components/Spinner";
import {
  getCompanyConfig,
  listSheetPreviewRows,
  type CompanyConfig,
  type SheetPreviewRow,
} from "../lib/supportApi";
import { useToast } from "../context/ToastContext";

type Props = {
  accessToken: string;
  companyId: string;
};

type InquiryFilter = "all" | "open" | "complete";

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function sheetUrlFromConfig(config: CompanyConfig | null): string {
  if (!config) return "";
  if (config.google_sheet_url) return config.google_sheet_url;
  if (config.google_sheet_id) {
    return `https://docs.google.com/spreadsheets/d/${config.google_sheet_id}/edit`;
  }
  return "";
}

export default function CompanySheets({ accessToken, companyId }: Props) {
  const toast = useToast();
  const [config, setConfig] = useState<CompanyConfig | null>(null);
  const [rows, setRows] = useState<SheetPreviewRow[]>([]);
  const [filter, setFilter] = useState<InquiryFilter>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const sheetUrl = useMemo(() => sheetUrlFromConfig(config), [config]);

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (opts?.silent) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setErr(null);
      try {
        const q = filter === "all" ? undefined : { inquiry: filter };
        const [nextConfig, nextRows] = await Promise.all([
          getCompanyConfig(accessToken, companyId),
          listSheetPreviewRows(accessToken, companyId, q),
        ]);
        setConfig(nextConfig);
        setRows(nextRows);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to load sheets";
        setErr(msg);
        toast.error(msg);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [accessToken, companyId, filter, toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <PageLoader message="Loading sheets..." />;
  }

  return (
    <div className="wa-inbox">
      <div className="wa-inbox__toolbar">
        <label className="wa-inbox__filter">
          <span>Inquiry</span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as InquiryFilter)}
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="complete">Complete</option>
          </select>
        </label>
        <button type="button" className="secondary" onClick={() => void load({ silent: true })}>
          {refreshing ? <Spinner size="sm" /> : "Refresh"}
        </button>
      </div>

      {err ? <div className="error">{err}</div> : null}

      <section className="sheet-preview-panel">
        <div className="sheet-preview-panel__header">
          <div>
            <h2>Google Sheets</h2>
            <p className="muted">
              {rows.length} preview row{rows.length === 1 ? "" : "s"} from the
              company conversation sheet.
            </p>
          </div>
          <div className="sheet-actions">
            <span className={`wa-badge ${config?.google_sheets_enabled ? "wa-badge--done" : "wa-badge--cold"}`}>
              {config?.google_sheets_enabled ? "Enabled" : "Disabled"}
            </span>
            {sheetUrl ? (
              <a className="secondary" href={sheetUrl} target="_blank" rel="noreferrer">
                Open Google Sheet
              </a>
            ) : null}
          </div>
        </div>

        {sheetUrl ? (
          <p className="muted">
            Linked sheet:{" "}
            <a href={sheetUrl} target="_blank" rel="noreferrer">
              {config?.google_sheet_id || sheetUrl}
            </a>
          </p>
        ) : (
          <p className="muted">No live Google Sheet is linked for this company yet.</p>
        )}

        <div className="table-scroll table-scroll--wide">
          <table className="companies sheet-preview-table">
            <thead>
              <tr>
                <th>ph no</th>
                <th>conversations (last 10 user messages)</th>
                <th>summary</th>
                <th>lead-type</th>
                <th>last message</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((r) => (
                  <tr key={r.conversation_id}>
                    <td>{r.customer_phone}</td>
                    <td className="sheet-preview-table__messages">
                      {r.conversations_last_10_user_messages || "-"}
                    </td>
                    <td>{r.summary || "-"}</td>
                    <td>
                      <span className={`wa-badge wa-badge--${r.lead_type || "cold"}`}>
                        {r.lead_type || "unlabeled"}
                      </span>
                      {r.inquiry_complete ? (
                        <span className="wa-badge wa-badge--done" style={{ marginLeft: 6 }}>
                          complete
                        </span>
                      ) : null}
                    </td>
                    <td>{formatTime(r.last_message_at) || "-"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>No sheet preview rows yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
