import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { companyIdFromUser } from "../lib/supabase";
import {
  listCompanies,
  portalChat,
  type ChatReply,
  type CompanySummary,
} from "../lib/api";
import ChatMarkdown from "../components/ChatMarkdown";
import { useToast } from "../context/ToastContext";

type Msg = {
  role: "user" | "assistant";
  text: string;
  meta?: string;
};

const STORAGE_KEY = "portal-chat-selected-company";

type Props = {
  accessToken: string;
  role: "admin" | "user";
  user: { app_metadata?: Record<string, unknown> };
};

export default function CompanyChat({ accessToken, role, user }: Props) {
  const toast = useToast();
  const userCompanyId = useMemo(() => companyIdFromUser(user), [user]);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>(() => {
    if (role === "user" && userCompanyId) return userCompanyId;
    try {
      return sessionStorage.getItem(STORAGE_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);

  const effectiveCompanyId =
    role === "user" ? userCompanyId ?? "" : selectedId;

  const selectedCompany = useMemo(
    () => companies.find((c) => c.id === effectiveCompanyId),
    [companies, effectiveCompanyId],
  );

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [msgs, busy]);

  const loadCompanies = useCallback(async () => {
    if (role !== "admin") return;
    setLoadErr(null);
    try {
      const rows = await listCompanies(accessToken);
      setCompanies(rows);
      setSelectedId((prev) => {
        if (prev && rows.some((r) => r.id === prev)) return prev;
        const stored =
          typeof sessionStorage !== "undefined"
            ? sessionStorage.getItem(STORAGE_KEY)
            : null;
        if (stored && rows.some((r) => r.id === stored)) return stored;
        return rows[0]?.id ?? "";
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load companies";
      setLoadErr(msg);
      toast.error(msg);
    }
  }, [accessToken, role, toast]);

  useEffect(() => {
    void loadCompanies();
  }, [loadCompanies]);

  useEffect(() => {
    if (role === "admin" && selectedId) {
      try {
        sessionStorage.setItem(STORAGE_KEY, selectedId);
      } catch {
        /* ignore */
      }
    }
  }, [role, selectedId]);

  function clearConversation() {
    setMsgs([]);
    setErr(null);
    toast.info("New chat — context cleared.");
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || busy || !effectiveCompanyId) return;
    setErr(null);
    setInput("");
    const historyPayload = msgs.map((m) => ({
      role: m.role,
      content: m.text,
    }));
    setMsgs((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const data: ChatReply = await portalChat(
        accessToken,
        effectiveCompanyId,
        text,
        historyPayload,
      );
      const srcHint =
        data.sources && data.sources.length > 0
          ? `sources: ${data.sources
              .slice(0, 3)
              .map((s) => s.file_name || "doc")
              .join(", ")}`
          : null;
      const meta = [
        data.response_type === "rag" ? "RAG" : "Fallback",
        data.detected_language && `lang: ${data.detected_language}`,
        data.top_score != null && `score: ${data.top_score.toFixed(3)}`,
        srcHint,
      ]
        .filter(Boolean)
        .join(" · ");
      setMsgs((m) => [
        ...m,
        { role: "assistant", text: data.answer, meta },
      ]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Chat failed";
      setErr(msg);
      toast.error(msg);
      setMsgs((m) => m.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void sendMessage();
  }

  if (role === "user" && !userCompanyId) {
    return (
      <div className="auth-page">
        <div className="card chat-shell">
          <h2 style={{ marginTop: 0 }}>Company not linked</h2>
          <p className="lead">
            Your Supabase user is missing{" "}
            <code>app_metadata.company_id</code>. Ask an admin to set it to
            your company UUID.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-gpt app-chat-panel">
      <aside className="chat-gpt-sidebar">
        <div className="chat-gpt-brand">Assistant</div>
        {role === "admin" && (
          <label className="chat-gpt-select-label">
            <span>Company (RAG context)</span>
            <select
              value={selectedId}
              onChange={(e) => {
                setSelectedId(e.target.value);
                clearConversation();
              }}
              disabled={!!loadErr || companies.length === 0}
            >
              {companies.length === 0 && <option value="">Loading…</option>}
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name || c.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {loadErr && <p className="error chat-gpt-sidebar-err">{loadErr}</p>}
        {selectedCompany && (
          <p className="chat-gpt-meta">
            <strong>{selectedCompany.display_name}</strong>
            <span className="chat-gpt-slug">{selectedCompany.name}</span>
          </p>
        )}
        <button
          type="button"
          className="secondary chat-gpt-new"
          onClick={clearConversation}
        >
          New chat
        </button>
      </aside>

      <section className="chat-gpt-main">
        <header className="chat-gpt-header">
          <h1>
            {selectedCompany
              ? selectedCompany.display_name
              : "Select a company"}
          </h1>
          <p className="chat-gpt-sub">
            Ask questions grounded in this tenant&apos;s indexed documents.
          </p>
        </header>

        <div className="chat-gpt-messages" ref={messagesRef}>
          {msgs.length === 0 && (
            <div className="chat-gpt-empty">
              <p>How can I help you today?</p>
              <p className="chat-gpt-hint">
                Answers use this company&apos;s indexed documents. Recent turns
                are sent for context; use <strong>New chat</strong> to reset.
              </p>
            </div>
          )}
          {msgs.map((m, i) => (
            <div
              key={i}
              className={`chat-gpt-bubble chat-gpt-bubble--${m.role}`}
            >
              <div className="chat-gpt-bubble-label">
                {m.role === "user" ? "You" : "Assistant"}
              </div>
              {m.role === "assistant" ? (
                <ChatMarkdown>{m.text}</ChatMarkdown>
              ) : (
                <div className="chat-gpt-bubble-text">{m.text}</div>
              )}
              {m.meta && (
                <div className="chat-gpt-bubble-meta">{m.meta}</div>
              )}
            </div>
          ))}
          {busy && (
            <div className="chat-gpt-bubble chat-gpt-bubble--assistant chat-gpt-typing">
              <span />
              <span />
              <span />
            </div>
          )}
          <div ref={endRef} />
        </div>

        {err && <p className="error chat-gpt-err">{err}</p>}

        <form className="chat-gpt-composer" onSubmit={onSubmit}>
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendMessage();
              }
            }}
            placeholder={
              effectiveCompanyId
                ? "Message — Enter to send, Shift+Enter for new line"
                : "Select a company first"
            }
            disabled={busy || !effectiveCompanyId}
          />
          <button
            className="primary chat-gpt-send"
            type="submit"
            disabled={busy || !effectiveCompanyId || !input.trim()}
          >
            Send
          </button>
        </form>
      </section>
    </div>
  );
}
