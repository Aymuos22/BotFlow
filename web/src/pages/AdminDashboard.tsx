import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fullOnboard,
  getLanguageCatalog,
  listCompanies,
  type CompanySummary,
  type LanguageOption,
} from "../lib/api";
import {
  createPortalUser,
  listPortalUsers,
  resetPortalUserPassword,
  type PortalUser,
} from "../lib/supportApi";
import { PageLoader } from "../components/Spinner";
import { useToast } from "../context/ToastContext";

const FALLBACK_LANGUAGE_CATALOG: LanguageOption[] = [
  { code: "english", label: "English", description: "" },
  { code: "hindi", label: "Hindi (Devanagari)", description: "" },
  { code: "hinglish", label: "Hinglish (Roman Hindi)", description: "" },
];
const MAX_BCRYPT_PASSWORD_BYTES = 72;

function utf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

function sortLangCodesByCatalog(catalog: LanguageOption[], codes: string[]): string[] {
  const order = catalog.map((c) => c.code);
  return [...codes].sort((a, b) => order.indexOf(a) - order.indexOf(b));
}

type AdminTab = "companies" | "users";

function statusBadgeClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "active") return "badge badge--active";
  if (s === "draft") return "badge badge--draft";
  return "badge badge--inactive";
}

function statusDotClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "active") return "status-dot status-dot--active";
  if (s === "draft") return "status-dot status-dot--draft";
  return "status-dot status-dot--inactive";
}

type Props = { accessToken: string };

export default function AdminDashboard({ accessToken }: Props) {
  const toast = useToast();
  const [tab, setTab] = useState<AdminTab>("companies");

  // ── Companies ──────────────────────────────────────────────────────
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [showOnboard, setShowOnboard] = useState(false);
  const [company_name, setCompanyName] = useState("");
  const [display_name, setDisplayName] = useState("");
  const [phone_number, setPhone] = useState("");
  const [default_language, setDefaultLang] = useState("english");
  const [supported_languages, setSupportedLangs] = useState<string[]>(["english"]);
  const [langCatalog, setLangCatalog] = useState<LanguageOption[]>(FALLBACK_LANGUAGE_CATALOG);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [formOk, setFormOk] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // ── Portal users ───────────────────────────────────────────────────
  const [portalUsers, setPortalUsers] = useState<PortalUser[]>([]);
  const [portalErr, setPortalErr] = useState<string | null>(null);
  const [pu_username, setPuUsername] = useState("");
  const [pu_password, setPuPassword] = useState("");
  const [puShowPassword, setPuShowPassword] = useState(false);
  const [pu_role, setPuRole] = useState<"admin" | "user">("user");
  const [pu_company_id, setPuCompanyId] = useState("");
  const [puBusy, setPuBusy] = useState(false);
  const [puOk, setPuOk] = useState<string | null>(null);
  const [resetUserId, setResetUserId] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetShowPassword, setResetShowPassword] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [adminInitialLoading, setAdminInitialLoading] = useState(true);

  function companyLabel(company: CompanySummary): string {
    return `${company.display_name || company.name} (${company.name})`;
  }

  async function refreshCompanies(opts?: { notifySuccess?: boolean }) {
    setLoadErr(null);
    try {
      setCompanies(await listCompanies(accessToken));
      if (opts?.notifySuccess) toast.success("Companies updated.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load companies";
      setLoadErr(msg);
      toast.error(msg);
    }
  }

  async function refreshPortalUsers(opts?: { notifySuccess?: boolean }) {
    setPortalErr(null);
    try {
      setPortalUsers(await listPortalUsers(accessToken));
      if (opts?.notifySuccess) toast.success("Portal users updated.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load users";
      setPortalErr(msg);
      toast.error(msg);
    }
  }

  useEffect(() => {
    setAdminInitialLoading(true);
    void Promise.all([refreshCompanies(), refreshPortalUsers()]).finally(() => {
      setAdminInitialLoading(false);
    });
  }, [accessToken]);

  useEffect(() => {
    void getLanguageCatalog()
      .then((rows) => {
        if (rows.length > 0) setLangCatalog(rows);
      })
      .catch(() => {
        /* keep fallback */
      });
  }, []);

  useEffect(() => {
    if (supported_languages.length > 0 && !supported_languages.includes(default_language)) {
      setDefaultLang(supported_languages[0]!);
    }
  }, [supported_languages, default_language]);

  async function onOnboard(e: FormEvent) {
    e.preventDefault();
    setFormErr(null);
    setFormOk(null);
    if (supported_languages.length === 0) {
      const msg = "Select at least one supported language.";
      setFormErr(msg);
      toast.error(msg);
      return;
    }
    if (!supported_languages.includes(default_language)) {
      const msg = "Default language must be one of the supported languages.";
      setFormErr(msg);
      toast.error(msg);
      return;
    }
    setBusy(true);
    try {
      await fullOnboard(accessToken, {
        company_name,
        display_name,
        phone_number,
        default_language,
        supported_languages: sortLangCodesByCatalog(langCatalog, supported_languages),
      });
      setFormOk("Company onboarded successfully.");
      toast.success("Company onboarded successfully.");
      setCompanyName("");
      setDisplayName("");
      setPhone("");
      setShowOnboard(false);
      await refreshCompanies();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Onboarding failed";
      setFormErr(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  if (adminInitialLoading) {
    return (
      <div className="stack dashboard-shell dashboard-shell--loading">
        <PageLoader message="Loading dashboard…" />
      </div>
    );
  }

  return (
    <div className="stack dashboard-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin dashboard</h1>
          <p className="lead" style={{ marginTop: "0.25rem" }}>
            Manage companies, users, and the assistant.
          </p>
        </div>
        <Link className="btn-chat-cta" to="/chat">
          Open assistant →
        </Link>
      </div>

      <div className="card card--wide">
        <div className="tabs">
          <button
            type="button"
            className={`tab-btn${tab === "companies" ? " tab-btn--active" : ""}`}
            onClick={() => setTab("companies")}
          >
            Companies
          </button>
          <button
            type="button"
            className={`tab-btn${tab === "users" ? " tab-btn--active" : ""}`}
            onClick={() => setTab("users")}
          >
            Portal users
          </button>
        </div>

        {/* ── Companies tab ── */}
        {tab === "companies" && (
          <div className="tab-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
              <p className="lead" style={{ margin: 0 }}>
                {companies.length === 0 && !loadErr
                  ? "No companies yet."
                  : `${companies.length} compan${companies.length === 1 ? "y" : "ies"}`}
              </p>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => void refreshCompanies({ notifySuccess: true })}
                >
                  Refresh
                </button>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    setShowOnboard((v) => !v);
                    setFormErr(null);
                    setFormOk(null);
                  }}
                >
                  {showOnboard ? "Cancel" : "+ Onboard company"}
                </button>
              </div>
            </div>

            {loadErr && <p className="error">{loadErr}</p>}
            {formOk && <p className="success-inline">{formOk}</p>}

            {showOnboard && (
              <div style={{ background: "var(--bg-base)", borderRadius: "var(--radius-md)", padding: "1.25rem", border: "1px solid var(--border)" }}>
                <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 700 }}>New company</h3>
                <form className="stack" onSubmit={onOnboard}>
                  <div className="grid-responsive">
                    <label>
                      <span>Company slug</span>
                      <input
                        type="text"
                        value={company_name}
                        onChange={(e) => setCompanyName(e.target.value)}
                        required
                        minLength={2}
                        placeholder="acme-corp"
                      />
                    </label>
                    <label>
                      <span>Display name</span>
                      <input
                        type="text"
                        value={display_name}
                        onChange={(e) => setDisplayName(e.target.value)}
                        required
                        minLength={2}
                        placeholder="Acme Corporation"
                      />
                    </label>
                    <label>
                      <span>WhatsApp phone (E.164)</span>
                      <input
                        type="text"
                        value={phone_number}
                        onChange={(e) => setPhone(e.target.value)}
                        required
                        placeholder="+919318492023"
                      />
                    </label>
                    <label style={{ gridColumn: "1 / -1" }}>
                      <span>Supported reply languages</span>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.5rem",
                          marginTop: "0.35rem",
                          padding: "0.5rem 0",
                        }}
                      >
                        {langCatalog.map((o) => (
                          <label
                            key={o.code}
                            style={{
                              display: "flex",
                              gap: "0.5rem",
                              alignItems: "flex-start",
                              fontWeight: "normal",
                              fontSize: "0.9rem",
                              cursor: "pointer",
                            }}
                            title={o.description}
                          >
                            <input
                              type="checkbox"
                              style={{ marginTop: "0.2rem" }}
                              checked={supported_languages.includes(o.code)}
                              onChange={() =>
                                setSupportedLangs((prev) => {
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
                              {o.description ? (
                                <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                                  {o.description}
                                </span>
                              ) : null}
                            </span>
                          </label>
                        ))}
                      </div>
                    </label>
                    <label>
                      <span>Default language</span>
                      <select
                        value={default_language}
                        onChange={(e) => setDefaultLang(e.target.value)}
                      >
                        {langCatalog
                          .filter((o) => supported_languages.includes(o.code))
                          .map((o) => (
                            <option key={o.code} value={o.code}>
                              {o.label}
                            </option>
                          ))}
                      </select>
                    </label>
                  </div>
                  {formErr && <p className="error">{formErr}</p>}
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="primary" type="submit" disabled={busy}>
                      {busy ? "Submitting…" : "Create company"}
                    </button>
                    <button type="button" className="secondary" onClick={() => setShowOnboard(false)}>
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}

            {companies.length > 0 && (
              <div className="table-scroll">
              <table className="companies">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Slug</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {companies.map((c) => (
                    <tr key={c.id}>
                      <td style={{ fontWeight: 600 }}>{c.display_name}</td>
                      <td><code>{c.name}</code></td>
                      <td>
                        <span className={statusBadgeClass(c.status)}>
                          <span className={statusDotClass(c.status)} style={{ width: 6, height: 6, marginRight: 4, verticalAlign: "middle", display: "inline-block", borderRadius: "50%" }} />
                          {c.status}
                        </span>
                      </td>
                      <td>
                        <Link className="support-manage-link" to={`/admin/companies/${c.id}`}>
                          Manage →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </div>
        )}

        {/* ── Portal users tab ── */}
        {tab === "users" && (
          <div className="tab-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
              <p className="lead" style={{ margin: 0 }}>
                {portalUsers.length} portal user{portalUsers.length !== 1 ? "s" : ""}
              </p>
              <button
                type="button"
                className="secondary"
                onClick={() => void refreshPortalUsers({ notifySuccess: true })}
              >
                Refresh
              </button>
            </div>

            {portalErr && <p className="error">{portalErr}</p>}
            {puOk && <p className="success-inline">{puOk}</p>}

            {portalUsers.length > 0 && (
              <div className="table-scroll">
              <table className="companies">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Role</th>
                    <th>Company</th>
                    <th>Active</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {portalUsers.map((u) => (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 600 }}>{u.username}</td>
                      <td>
                        <span className={`badge ${u.role === "admin" ? "badge--active" : "badge--draft"}`}>
                          {u.role}
                        </span>
                      </td>
                      <td>
                        {u.company_id
                          ? <code style={{ fontSize: "0.8rem" }}>{u.company_id.slice(0, 8)}…</code>
                          : <span style={{ color: "var(--text-muted)" }}>—</span>}
                      </td>
                      <td>
                        <span className={`badge ${u.is_active ? "badge--active" : "badge--inactive"}`}>
                          {u.is_active ? "yes" : "no"}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => {
                            setResetUserId(u.id);
                            setResetPassword("");
                            setPortalErr(null);
                            setPuOk(null);
                          }}
                        >
                          Reset password
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}

            {resetUserId && (
              <div style={{ background: "var(--bg-base)", borderRadius: "var(--radius-md)", padding: "1.25rem", border: "1px solid var(--border)" }}>
                <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 700 }}>
                  Reset password for {portalUsers.find((u) => u.id === resetUserId)?.username ?? "portal user"}
                </h3>
                <form
                  className="stack"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setPuOk(null);
                    setPortalErr(null);
                    if (resetPassword.length < 8) {
                      const msg = "Password must be at least 8 characters.";
                      setPortalErr(msg);
                      toast.error(msg);
                      return;
                    }
                    if (utf8ByteLength(resetPassword) > MAX_BCRYPT_PASSWORD_BYTES) {
                      const msg = "Password must be 72 bytes or fewer.";
                      setPortalErr(msg);
                      toast.error(msg);
                      return;
                    }
                    setResetBusy(true);
                    void (async () => {
                      try {
                        await resetPortalUserPassword(accessToken, resetUserId, resetPassword);
                        setPuOk("Password reset. Share the new password with the user.");
                        toast.success("Password reset.");
                        setResetUserId("");
                        setResetPassword("");
                        await refreshPortalUsers();
                      } catch (err) {
                        const msg = err instanceof Error ? err.message : "Reset failed";
                        setPortalErr(msg);
                        toast.error(msg);
                      } finally {
                        setResetBusy(false);
                      }
                    })();
                  }}
                >
                  <label>
                    <span>New password</span>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <input
                        type={resetShowPassword ? "text" : "password"}
                        value={resetPassword}
                        onChange={(e) => setResetPassword(e.target.value)}
                        required
                        minLength={8}
                        maxLength={72}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setResetShowPassword((v) => !v)}
                      >
                        {resetShowPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                  </label>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button className="primary" type="submit" disabled={resetBusy}>
                      {resetBusy ? "Resetting..." : "Reset password"}
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => {
                        setResetUserId("");
                        setResetPassword("");
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}

            <div style={{ background: "var(--bg-base)", borderRadius: "var(--radius-md)", padding: "1.25rem", border: "1px solid var(--border)" }}>
              <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 700 }}>Create portal user</h3>
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  setPuOk(null);
                  setPortalErr(null);
                  if (pu_role === "user" && !pu_company_id.trim()) {
                    const msg = "Select a company for role user.";
                    setPortalErr(msg);
                    toast.error(msg);
                    return;
                  }
                  if (pu_password.length < 8) {
                    const msg = "Password must be at least 8 characters.";
                    setPortalErr(msg);
                    toast.error(msg);
                    return;
                  }
                  if (utf8ByteLength(pu_password) > MAX_BCRYPT_PASSWORD_BYTES) {
                    const msg = "Password must be 72 bytes or fewer.";
                    setPortalErr(msg);
                    toast.error(msg);
                    return;
                  }
                  setPuBusy(true);
                  void (async () => {
                    try {
                      await createPortalUser(accessToken, {
                        username: pu_username.trim(),
                        password: pu_password,
                        role: pu_role,
                        company_id: pu_role === "user" ? pu_company_id.trim() : null,
                      });
                      setPuOk("User created.");
                      toast.success("Portal user created.");
                      setPuUsername("");
                      setPuPassword("");
                      setPuCompanyId("");
                      await refreshPortalUsers();
                    } catch (err) {
                      const msg = err instanceof Error ? err.message : "Create failed";
                      setPortalErr(msg);
                      toast.error(msg);
                    } finally {
                      setPuBusy(false);
                    }
                  })();
                }}
              >
                <div className="grid-responsive">
                  <label>
                    <span>Username</span>
                    <input
                      type="text"
                      value={pu_username}
                      onChange={(e) => setPuUsername(e.target.value)}
                      required
                      minLength={2}
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    <span>Password</span>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <input
                        type={puShowPassword ? "text" : "password"}
                        value={pu_password}
                        onChange={(e) => setPuPassword(e.target.value)}
                        required
                        minLength={8}
                        maxLength={72}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setPuShowPassword((v) => !v)}
                      >
                        {puShowPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                  </label>
                  <label>
                    <span>Role</span>
                    <select value={pu_role} onChange={(e) => setPuRole(e.target.value as "admin" | "user")}>
                      <option value="user">user (scoped to company)</option>
                      <option value="admin">admin</option>
                    </select>
                  </label>
                  {pu_role === "user" && (
                    <label>
                      <span>Company</span>
                      <select
                        value={pu_company_id}
                        onChange={(e) => setPuCompanyId(e.target.value)}
                        required
                        disabled={companies.length === 0}
                      >
                        <option value="">
                          {companies.length === 0 ? "No companies available" : "Select company"}
                        </option>
                        {companies.map((c) => (
                          <option key={c.id} value={c.id}>
                            {companyLabel(c)}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>
                <div>
                  <button className="primary" type="submit" disabled={puBusy}>
                    {puBusy ? "Creating…" : "Create user"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
