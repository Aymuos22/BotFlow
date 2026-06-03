import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import {
  getInboxMessages,
  listInboxConversations,
  patchInboxConversation,
  sendInboxMessage,
  type InboxConversation,
  type InboxMessage,
} from "../lib/supportApi";
import ChatMarkdown from "../components/ChatMarkdown";
import { PageLoader, Spinner } from "../components/Spinner";
import { useToast } from "../context/ToastContext";

type Props = {
  accessToken: string;
  companyId: string;
};

type LeadFilter = "all" | "hot" | "warm" | "cold" | "unlabeled";

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

function formatBubbleTime(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function messageDateKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function formatDateSeparator(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffMs = today.getTime() - msgDay.getTime();
  const diffDays = Math.round(diffMs / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: diffDays > 365 ? "numeric" : undefined });
}

function warmthLabel(w: string | null | undefined): string {
  if (!w) return "";
  return w.charAt(0).toUpperCase() + w.slice(1);
}

function senderLabel(senderType: string): string {
  if (senderType === "customer") return "Customer";
  if (senderType === "agent") return "You";
  if (senderType === "bot") return "Bot";
  return senderType;
}

function downloadWorkbook(filename: string, sheets: Record<string, Record<string, unknown>[]>) {
  const wb = XLSX.utils.book_new();
  for (const [sheetName, rows] of Object.entries(sheets)) {
    const ws = XLSX.utils.json_to_sheet(rows);
    XLSX.utils.book_append_sheet(wb, ws, sheetName.slice(0, 31) || "Sheet1");
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

export default function CompanyInbox({ accessToken, companyId }: Props) {
  const toast = useToast();
  const [rows, setRows] = useState<InboxConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [inquiryFilter, setInquiryFilter] = useState<"all" | "open" | "complete">(
    "all",
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [compose, setCompose] = useState("");
  const [search, setSearch] = useState("");
  const [leadFilter, setLeadFilter] = useState<LeadFilter>("all");
  const [sendBusy, setSendBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [patchBusy, setPatchBusy] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  /** When true, new messages or polling may scroll the thread to the end. */
  const stickToBottomRef = useRef(true);

  const selected = useMemo(
    () => rows.find((r) => r.id === selectedId) ?? null,
    [rows, selectedId],
  );

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      const matchesSearch =
        !q ||
        r.customer_phone.toLowerCase().includes(q) ||
        (r.last_message_preview || "").toLowerCase().includes(q);
      const lw = (r.lead_warmth || "").toLowerCase();
      const matchesLead =
        leadFilter === "all"
          ? true
          : leadFilter === "unlabeled"
            ? !lw
            : lw === leadFilter;
      return matchesSearch && matchesLead;
    });
  }, [rows, search, leadFilter]);

  const loadList = useCallback(async () => {
    setErr(null);
    try {
      const q = inquiryFilter === "all" ? undefined : { inquiry: inquiryFilter };
      const data = await listInboxConversations(accessToken, companyId, q);
      setRows(data);
      setSelectedId((prev) => {
        if (prev && !data.some((d) => d.id === prev)) return data[0]?.id ?? null;
        return prev;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load inbox";
      setErr(msg);
    } finally {
      setLoading(false);
    }
  }, [accessToken, companyId, inquiryFilter]);

  const loadMessages = useCallback(
    async (convId: string, opts?: { silent?: boolean }) => {
      const silent = opts?.silent === true;
      if (!silent) setMsgLoading(true);
      try {
        const data = await getInboxMessages(accessToken, companyId, convId);
        setMessages(data);
      } catch (e) {
        if (!silent) {
          toast.error(e instanceof Error ? e.message : "Failed to load messages");
        }
      } finally {
        if (!silent) setMsgLoading(false);
      }
    },
    [accessToken, companyId, toast],
  );

  useEffect(() => {
    void loadList();
  }, [loadList]);

  // Faster thread refresh for a WhatsApp-like feel.
  useEffect(() => {
    if (!selectedId) return;
    const refreshThread = () => {
      if (document.visibilityState !== "visible") return;
      void loadMessages(selectedId, { silent: true });
    };
    const t = window.setInterval(refreshThread, 4_000);
    return () => window.clearInterval(t);
  }, [loadMessages, selectedId]);

  // Sidebar refresh can be slower than the active thread refresh.
  useEffect(() => {
    const t = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void loadList();
    }, 10_000);
    return () => window.clearInterval(t);
  }, [loadList]);

  // Immediate refresh when user focuses the tab/window.
  useEffect(() => {
    const refreshNow = () => {
      if (document.visibilityState !== "visible") return;
      void loadList();
      if (selectedId) void loadMessages(selectedId, { silent: true });
    };
    window.addEventListener("focus", refreshNow);
    document.addEventListener("visibilitychange", refreshNow);
    return () => {
      window.removeEventListener("focus", refreshNow);
      document.removeEventListener("visibilitychange", refreshNow);
    };
  }, [loadList, loadMessages, selectedId]);

  useEffect(() => {
    if (selectedId) {
      stickToBottomRef.current = true;
      setMessages([]);
      void loadMessages(selectedId, { silent: false });
    } else {
      setMessages([]);
    }
  }, [selectedId, loadMessages]);

  const onThreadScroll = useCallback(() => {
    const el = threadRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    stickToBottomRef.current = nearBottom;
  }, []);

  useEffect(() => {
    if (!stickToBottomRef.current) return;
    endRef.current?.scrollIntoView({ behavior: "auto" });
  }, [messages]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!selectedId || !compose.trim() || sendBusy) return;
    setSendBusy(true);
    try {
      const sent = await sendInboxMessage(accessToken, companyId, selectedId, compose.trim());
      setCompose("");
      stickToBottomRef.current = true;
      setMessages((prev) => [...prev, sent]);
      await loadMessages(selectedId, { silent: true });
      await loadList();
      toast.success("Message sent");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSendBusy(false);
    }
  }

  async function applyLead(lead: string) {
    if (!selectedId) return;
    const v = lead === "" ? null : lead;
    setPatchBusy(true);
    try {
      const updated = await patchInboxConversation(
        accessToken,
        companyId,
        selectedId,
        { lead_warmth: v },
      );
      setRows((prev) => prev.map((r) => (r.id === updated.id ? { ...r, ...updated } : r)));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    } finally {
      setPatchBusy(false);
    }
  }

  async function toggleInquiryComplete(next: boolean) {
    if (!selectedId) return;
    setPatchBusy(true);
    try {
      const updated = await patchInboxConversation(
        accessToken,
        companyId,
        selectedId,
        { inquiry_complete: next },
      );
      setRows((prev) => prev.map((r) => (r.id === updated.id ? { ...r, ...updated } : r)));
      toast.success(next ? "Marked inquiry complete" : "Reopened");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    } finally {
      setPatchBusy(false);
    }
  }

  async function exportLeadsToXlsx() {
    if (filteredRows.length === 0) {
      toast.error("No leads match current filters.");
      return;
    }
    setExportBusy(true);
    try {
      const messageLists = await Promise.all(
        filteredRows.map(async (row) => {
          try {
            const msgs = await getInboxMessages(accessToken, companyId, row.id);
            return { conversation_id: row.id, messages: msgs };
          } catch {
            return { conversation_id: row.id, messages: [] as InboxMessage[] };
          }
        }),
      );
      const messageMap = new Map(
        messageLists.map((x) => [x.conversation_id, x.messages] as const),
      );

      const leadRows = filteredRows.map((r) => ({
        conversation_id: r.id,
        company_id: r.company_id,
        customer_phone: r.customer_phone,
        lead_warmth: r.lead_warmth ?? "",
        lead_warmth_locked: r.lead_warmth_locked ? "yes" : "no",
        inquiry_complete: r.inquiry_complete ? "yes" : "no",
        inquiry_completed_at: r.inquiry_completed_at ?? "",
        current_mode: r.current_mode,
        status: r.status,
        detected_language: r.detected_language ?? "",
        assigned_agent_id: r.assigned_agent_id ?? "",
        last_message_at: r.last_message_at ?? "",
        last_message_preview: r.last_message_preview ?? "",
        created_at: r.created_at,
        updated_at: r.updated_at,
        total_messages: (messageMap.get(r.id) || []).length,
      }));

      const messageRows = filteredRows.flatMap((r) =>
        (messageMap.get(r.id) || []).map((m) => ({
          conversation_id: r.id,
          customer_phone: r.customer_phone,
          message_id: m.id,
          sender_type: m.sender_type,
          response_type: m.response_type ?? "",
          language: m.language ?? "",
          created_at: m.created_at,
          external_message_id: m.external_message_id ?? "",
          message_text: m.message_text,
        })),
      );

      const ts = new Date().toISOString().replaceAll(":", "-");
      downloadWorkbook(`inbox-leads-${companyId}-${leadFilter}-${ts}.xlsx`, {
        leads: leadRows,
        messages: messageRows,
      });
      toast.success("Lead export started.");
    } finally {
      setExportBusy(false);
    }
  }

  if (loading) {
    return <PageLoader message="Loading conversations..." />;
  }

  return (
    <div className={`wa-inbox${fullscreen ? " wa-inbox--fullscreen" : ""}`}>
      {err && <p className="error" style={{ margin: "0 0 0.5rem" }}>{err}</p>}

      <div className="wa-inbox__toolbar" style={{ marginBottom: "0.75rem" }}>
        <label className="wa-inbox__filter">
          <span>View</span>
          <select
            value={inquiryFilter}
            onChange={(e) => {
              setInquiryFilter(e.target.value as "all" | "open" | "complete");
              setSelectedId(null);
            }}
          >
            <option value="all">All threads</option>
            <option value="open">Open inquiries</option>
            <option value="complete">Completed inquiries</option>
          </select>
        </label>
        <label className="wa-inbox__filter">
          <span>Search</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Phone or message"
          />
        </label>
        <label className="wa-inbox__filter">
          <span>Lead type</span>
          <select
            value={leadFilter}
            onChange={(e) => setLeadFilter(e.target.value as LeadFilter)}
          >
            <option value="all">All leads</option>
            <option value="hot">Hot</option>
            <option value="warm">Warm</option>
            <option value="cold">Cold</option>
            <option value="unlabeled">Unlabeled</option>
          </select>
        </label>
        <button
          type="button"
          className="secondary"
          disabled={exportBusy}
          onClick={() => void exportLeadsToXlsx()}
        >
          {exportBusy ? "Preparing..." : "Download Leads XLSX"}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            void loadList();
            if (selectedId) {
              stickToBottomRef.current = true;
              void loadMessages(selectedId, { silent: false });
            }
          }}
        >
          Refresh
        </button>
      </div>

      <div className="wa-inbox__panes">
        <aside className="wa-inbox__sidebar">
          {filteredRows.length === 0 && (
            <p style={{ padding: "0.5rem", color: "var(--text-secondary)" }}>
              {rows.length === 0
                ? "No conversations yet. Customer WhatsApp messages will show here."
                : "No leads match the current search/filter."}
            </p>
          )}
          <ul className="wa-inbox__list">
            {filteredRows.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className={
                    "wa-inbox__row" + (r.id === selectedId ? " wa-inbox__row--active" : "")
                  }
                  onClick={() => setSelectedId(r.id)}
                >
                  <div className="wa-inbox__row-top">
                    <span className="wa-avatar" aria-hidden>
                      {r.customer_phone.replace(/\D/g, "").slice(-2)}
                    </span>
                    <span className="wa-inbox__phone">{r.customer_phone}</span>
                    {r.lead_warmth && (
                      <span className={"wa-badge wa-badge--" + r.lead_warmth}>
                        {warmthLabel(r.lead_warmth)}
                      </span>
                    )}
                    {r.inquiry_complete && (
                      <span className="wa-badge wa-badge--done" title="Inquiry complete">
                        Done
                      </span>
                    )}
                  </div>
                  <div className="wa-inbox__preview">{r.last_message_preview || "-"}</div>
                  <div className="wa-inbox__ts">{formatTime(r.last_message_at)}</div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="wa-inbox__main">
          {!selectedId && (
            <div className="wa-inbox__empty">
              <p className="lead">Select a conversation</p>
            </div>
          )}

          {selectedId && selected && (
            <>
              <header className="wa-inbox__header">
                <div>
                  <h2 className="wa-inbox__title">{selected.customer_phone}</h2>
                  <p style={{ margin: "0.15rem 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    Mode: <strong>{selected.current_mode}</strong>
                    {selected.inquiry_complete && selected.inquiry_completed_at && (
                      <>
                        {" · "}
                        Completed {formatTime(selected.inquiry_completed_at)}
                      </>
                    )}
                  </p>
                </div>
                <div className="wa-inbox__actions">
                  <button
                    type="button"
                    title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
                    onClick={() => setFullscreen((f) => !f)}
                    style={{
                      background: "none",
                      border: "1px solid var(--wa-border)",
                      borderRadius: "8px",
                      cursor: "pointer",
                      padding: "0.3rem 0.5rem",
                      color: "var(--wa-subtext)",
                      fontSize: "1rem",
                      lineHeight: 1,
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    {fullscreen ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/></svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8V5a2 2 0 0 1 2-2h3"/><path d="M16 3h3a2 2 0 0 1 2 2v3"/><path d="M21 16v3a2 2 0 0 1-2 2h-3"/><path d="M8 21H5a2 2 0 0 1-2-2v-3"/></svg>
                    )}
                  </button>
                  <label
                    title={
                      selected.lead_warmth_locked
                        ? "Manual: choose - to clear and let AI update from new messages."
                        : "AI updates from customer messages; choose - to let AI change this again after a manual pick."
                    }
                  >
                    Lead
                    {selected.lead_warmth_locked ? " (manual)" : ""}
                    <select
                      value={selected.lead_warmth ?? ""}
                      disabled={patchBusy}
                      onChange={(e) => void applyLead(e.target.value)}
                    >
                      <option value="">-</option>
                      <option value="hot">Hot</option>
                      <option value="warm">Warm</option>
                      <option value="cold">Cold</option>
                    </select>
                  </label>
                  <label className="wa-inbox__check">
                    <input
                      type="checkbox"
                      checked={selected.inquiry_complete}
                      disabled={patchBusy}
                      onChange={(e) => void toggleInquiryComplete(e.target.checked)}
                    />
                    Inquiry complete
                  </label>
                </div>
              </header>

              <div
                className="wa-inbox__thread"
                ref={threadRef}
                onScroll={onThreadScroll}
              >
                {msgLoading && messages.length === 0 && (
                  <div className="wa-inbox__thread-loading">
                    <Spinner label="Loading messages..." />
                  </div>
                )}
                {!msgLoading || messages.length > 0
                  ? (() => {
                    let lastDateKey = "";
                    return messages.map((m) => {
                      const dateKey = messageDateKey(m.created_at);
                      const showSeparator = dateKey !== lastDateKey;
                      lastDateKey = dateKey;
                      const out = m.sender_type !== "customer";
                      return (
                        <div key={m.id}>
                          {showSeparator && (
                            <div style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "0.5rem",
                              margin: "1rem 0 0.5rem",
                              color: "var(--text-secondary)",
                              fontSize: "0.78rem",
                            }}>
                              <div style={{ flex: 1, height: 1, background: "var(--wa-border)" }} />
                              <span style={{
                                padding: "0.15rem 0.65rem",
                                borderRadius: "999px",
                                background: "var(--wa-border)",
                                whiteSpace: "nowrap",
                              }}>
                                {formatDateSeparator(m.created_at)}
                              </span>
                              <div style={{ flex: 1, height: 1, background: "var(--wa-border)" }} />
                            </div>
                          )}
                          <div
                            className={
                              "wa-bubble" + (out ? " wa-bubble--out" : " wa-bubble--in")
                            }
                          >
                            <div className="wa-bubble__meta">
                              {senderLabel(m.sender_type)}
                              {m.response_type && (
                                <span style={{ color: "var(--text-muted)" }}> · {m.response_type}</span>
                              )}
                            </div>
                            <div className="wa-bubble__body">
                              {m.sender_type === "bot" ? (
                                <ChatMarkdown text={m.message_text} />
                              ) : (
                                <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{m.message_text}</p>
                              )}
                            </div>
                            <div className="wa-bubble__time">{formatBubbleTime(m.created_at)}</div>
                          </div>
                        </div>
                      );
                    });
                  })()
                  : null}
                <div ref={endRef} />
              </div>

              <form className="wa-inbox__compose" onSubmit={onSend}>
                <textarea
                  rows={2}
                  placeholder="Type a WhatsApp message to the customer..."
                  value={compose}
                  onChange={(e) => setCompose(e.target.value)}
                  disabled={sendBusy}
                />
                <button type="submit" className="primary" disabled={sendBusy || !compose.trim()}>
                  {sendBusy ? "Sending..." : "Send"}
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
