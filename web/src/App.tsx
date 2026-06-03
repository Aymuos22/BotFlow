import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import type { Session, User } from "@supabase/supabase-js";
import { supabase, appRoleFromUser, companyIdFromUser } from "./lib/supabase";
import type { PortalLoginResponse, PortalLoginUser } from "./lib/api";
import { PageLoader } from "./components/Spinner";
import Layout from "./components/Layout";
import type { SidebarLink } from "./components/Sidebar";
import Login from "./pages/Login";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import AdminDashboard from "./pages/AdminDashboard";
import AdminInbox from "./pages/AdminInbox";
import CompanySupport from "./pages/CompanySupport";
import CompanyChat from "./pages/CompanyChat";
import CompanyInbox from "./pages/CompanyInbox";
import CompanySheets from "./pages/CompanySheets";
import CompanyFollowups from "./pages/CompanyFollowups";
import CompanyCampaigns from "./pages/CompanyCampaigns";
import PortalStaticDoc from "./pages/PortalStaticDoc";
import PlaceholderPage from "./pages/PlaceholderPage";
import { ToastProvider, useToast } from "./context/ToastContext";
import brandLogo from "../logo/logo.jpeg";

const PORTAL_SESSION_KEY = "mindorax.portalSession";

type AuthUser = Pick<User, "app_metadata">;

type PortalSession = {
  access_token: string;
  user: AuthUser;
};

function Icon({ children }: { children: React.ReactNode }) {
  return <span className="nav-svg">{children}</span>;
}

// ── Icons ────────────────────────────────────────────────────────────────────

const dashboardIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="8" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="15" width="7" height="6" rx="1" />
    </svg>
  </Icon>
);

const companiesIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 21h18" />
      <path d="M5 21V5a2 2 0 0 1 2-2h7v18" />
      <path d="M14 8h3a2 2 0 0 1 2 2v11" />
      <path d="M8 7h2M8 11h2M8 15h2" />
    </svg>
  </Icon>
);

const assistantIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
      <path d="M8 10h8M8 14h5" />
    </svg>
  </Icon>
);

const inboxIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </svg>
  </Icon>
);

const sheetsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8M8 17h8M8 9h2" />
    </svg>
  </Icon>
);

const followupsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
      <path d="M12 6v6l4 2" />
    </svg>
  </Icon>
);

const campaignsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 11v2a2 2 0 0 0 2 2h3" />
      <path d="M7 13V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v8" />
      <path d="M7 21h10a2 2 0 0 0 2-2v-4H5v4a2 2 0 0 0 2 2z" />
      <path d="M18 11h.01" />
    </svg>
  </Icon>
);

const integrationsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22v-6" />
      <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
      <path d="M9 12h6" />
      <circle cx="12" cy="16" r="2" />
      <path d="M19 12h-1a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h1" />
      <path d="M5 12H4a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h1" />
    </svg>
  </Icon>
);

const auditIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h2" />
      <path d="M8 17h8" />
      <path d="M8 9h2" />
    </svg>
  </Icon>
);

const automationsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
      <path d="m5.6 5.6 2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
    </svg>
  </Icon>
);

const insightsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M7 12v5" />
      <path d="M12 7v10" />
      <path d="M17 9v8" />
    </svg>
  </Icon>
);

const teamIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  </Icon>
);

const privacyIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  </Icon>
);

const termsIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M10 12h4M10 16h4" />
    </svg>
  </Icon>
);

const cookieIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5" />
      <path d="M8.5 8.5h.01M16 9.5h.01M12 16h.01" />
    </svg>
  </Icon>
);

const lockIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  </Icon>
);

const accessibilityIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="5" r="1" />
      <path d="M12 8v5" />
      <path d="M8 13h8" />
      <path d="M9 19h6" />
    </svg>
  </Icon>
);

const bookIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  </Icon>
);

const mailIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <path d="m22 6-10 7L2 6" />
    </svg>
  </Icon>
);

const globeIcon = (
  <Icon>
    <svg viewBox="0 0 24 24" fill="none" aria-hidden stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  </Icon>
);

// ── Shared nav sections (same for admin & user) ───────────────────────────

const conversationsNav: SidebarLink[] = [
  {
    sectionBefore: "Conversations",
    to: "/inbox",
    label: "History",
    icon: inboxIcon,
  },
];

const operationsNav: SidebarLink[] = [
  {
    sectionBefore: "Operations",
    to: "/campaigns",
    label: "Campaign Manager",
    icon: campaignsIcon,
  },
  {
    to: "/followups",
    label: "Follow-up Rules",
    icon: automationsIcon,
  },
  {
    to: "/operations/audience",
    label: "Audience Manager",
    icon: teamIcon,
  },
];

const developersNav: SidebarLink[] = [
  {
    sectionBefore: "Developers",
    to: "/developer/api-key",
    label: "API Key",
    icon: lockIcon,
  },
  {
    to: "/developer/webhooks",
    label: "Webhooks",
    icon: integrationsIcon,
  },
  {
    to: "/developer/logs",
    label: "Logs",
    icon: auditIcon,
  },
  {
    to: "/developer/code-mode",
    label: "Code Mode",
    icon: insightsIcon,
  },
];

const helpNav: SidebarLink[] = [
  {
    sectionBefore: "Help",
    to: "__ext/discord__",
    label: "Discord Community",
    icon: globeIcon,
    externalHref: "https://discord.gg/mindoraxai",
  },
  {
    to: "__ext/docs__",
    label: "Documentation",
    icon: bookIcon,
    externalHref: "https://docs.mindoraxai.com",
  },
  {
    to: "__ext/versity__",
    label: "Mindorax Versity",
    icon: accessibilityIcon,
    externalHref: "https://versity.mindoraxai.com",
  },
  {
    to: "__ext/partner__",
    label: "Hire a Partner",
    icon: mailIcon,
    externalHref: "mailto:partners@mindoraxai.com?subject=Partner%20inquiry",
  },
];

const planNav: SidebarLink[] = [
  {
    sectionBefore: "Account",
    to: "/billing",
    label: "Current Plan",
    icon: insightsIcon,
  },
];

function portalUserToAuthUser(user: PortalLoginUser): AuthUser {
  return {
    app_metadata: {
      role: user.role,
      company_id: user.company_id,
      username: user.username,
      portal_user_id: user.id,
    },
  };
}

function portalLoginToSession(login: PortalLoginResponse): PortalSession {
  return {
    access_token: login.access_token,
    user: portalUserToAuthUser(login.user),
  };
}

function loadPortalSession(): PortalSession | null {
  try {
    const raw = localStorage.getItem(PORTAL_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PortalLoginResponse;
    if (!parsed?.access_token || !parsed?.user?.role) return null;
    return portalLoginToSession(parsed);
  } catch {
    return null;
  }
}

function savePortalSession(login: PortalLoginResponse): PortalSession {
  localStorage.setItem(PORTAL_SESSION_KEY, JSON.stringify(login));
  return portalLoginToSession(login);
}

function clearPortalSession() {
  localStorage.removeItem(PORTAL_SESSION_KEY);
}

function roleOrNull(u: AuthUser | null): "admin" | "user" | null {
  if (!u) return null;
  return appRoleFromUser(u);
}

function userLabel(user: AuthUser | null): string {
  const meta = user?.app_metadata || {};
  const username = meta.username;
  if (typeof username === "string" && username) return username;
  const email = (user as User | null)?.email;
  if (typeof email === "string" && email) return email;
  return "Portal user";
}

function MissingRole({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="auth-page">
      <div className="card" style={{ maxWidth: 520 }}>
        <h2 style={{ marginTop: 0 }}>Role not configured</h2>
        <p className="lead">
          Your account has no <code>app_metadata.role</code> set. Contact an
          administrator to assign <code>admin</code> or <code>user</code>.
        </p>
        <button type="button" className="secondary" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </div>
  );
}

function Shell() {
  const toast = useToast();
  const [session, setSession] = useState<Session | null>(null);
  const [portalSession, setPortalSession] = useState<PortalSession | null>(() =>
    loadPortalSession(),
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, s) => {
      if (s) setPortalSession(null);
      setSession(s);
    });
    return () => subscription.unsubscribe();
  }, []);

  const activeSession = portalSession ?? session;
  const user = portalSession?.user ?? session?.user ?? null;
  const role = roleOrNull(user);
  const companyId = user ? companyIdFromUser(user) : null;

  const links = useMemo<SidebarLink[]>(() => {
    if (role === "admin") {
      return [
        { to: "/dashboard", label: "Dashboard", icon: dashboardIcon },
        { to: "/admin", label: "Companies", icon: companiesIcon },
        { to: "/chat", label: "Assistant", icon: assistantIcon },
        {
          sectionBefore: "Conversations",
          to: "/admin/inbox",
          label: "All Inboxes",
          icon: inboxIcon,
        },
        ...operationsNav,
        ...developersNav,
        ...helpNav,
        ...planNav,
      ];
    }
    if (role === "user") {
      return [
        { to: "/dashboard", label: "Dashboard", icon: dashboardIcon },
        { to: "/chat", label: "Assistant", icon: assistantIcon },
        ...(companyId ? [{ to: "/sheets", label: "Sheets", icon: sheetsIcon }] : []),
        ...conversationsNav,
        ...operationsNav,
        ...developersNav,
        ...helpNav,
        ...planNav,
      ];
    }
    return [];
  }, [role, companyId]);

  const logout = () => {
    clearPortalSession();
    setPortalSession(null);
    void supabase.auth.signOut().then(() => {
      setSession(null);
      toast.info("Signed out.");
    });
  };

  if (loading) {
    return (
      <div className="app-loading">
        <PageLoader message="Signing you in..." />
      </div>
    );
  }

  if (!activeSession || !role) {
    return (
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route
          path="/login"
          element={
            activeSession && !role ? (
              <MissingRole onLogout={logout} />
            ) : (
              <Login
                onPortalLogin={(login) => {
                  void supabase.auth.signOut();
                  setSession(null);
                  setPortalSession(savePortalSession(login));
                }}
              />
            )
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  return (
    <Layout
      links={links}
      logoSrc={brandLogo}
      userLabel={userLabel(user)}
      role={role}
      onLogout={logout}
    >
      <Routes>
        <Route
          path="/dashboard"
          element={
            <Dashboard
              accessToken={activeSession.access_token}
              role={role}
              companyId={companyId}
            />
          }
        />
        <Route
          path="/admin"
          element={
            role !== "admin" ? (
              <Navigate to="/chat" replace />
            ) : (
              <AdminDashboard accessToken={activeSession.access_token} />
            )
          }
        />
        <Route
          path="/admin/inbox"
          element={
            role !== "admin" ? (
              <Navigate to="/inbox" replace />
            ) : (
              <AdminInbox accessToken={activeSession.access_token} />
            )
          }
        />
        <Route
          path="/admin/companies/:companyId"
          element={
            role !== "admin" ? (
              <Navigate to="/chat" replace />
            ) : (
              <CompanySupport accessToken={activeSession.access_token} />
            )
          }
        />
        <Route
          path="/chat"
          element={
            <CompanyChat
              accessToken={activeSession.access_token}
              role={role}
              user={user}
            />
          }
        />
        <Route
          path="/inbox"
          element={
            role === "user" && companyId ? (
              <CompanyInbox
                accessToken={activeSession.access_token}
                companyId={companyId}
              />
            ) : (
              <Navigate to={role === "admin" ? "/admin" : "/chat"} replace />
            )
          }
        />
        <Route
          path="/sheets"
          element={
            role === "user" && companyId ? (
              <CompanySheets
                accessToken={activeSession.access_token}
                companyId={companyId}
              />
            ) : (
              <Navigate to={role === "admin" ? "/admin" : "/chat"} replace />
            )
          }
        />
        <Route
          path="/followups"
          element={
            role === "user" && companyId ? (
              <CompanyFollowups accessToken={activeSession.access_token} companyId={companyId} />
            ) : (
              <Navigate to={role === "admin" ? "/admin" : "/chat"} replace />
            )
          }
        />
        <Route
          path="/campaigns"
          element={
            companyId ? (
              <CompanyCampaigns accessToken={activeSession.access_token} companyId={companyId} />
            ) : (
              <Navigate to={role === "admin" ? "/admin" : "/chat"} replace />
            )
          }
        />
        {/* Operations */}
        <Route path="/operations/batch-calling" element={<PlaceholderPage title="Batch Calling" description="Send bulk WhatsApp calls to your audience. Coming up shortly." />} />
        <Route path="/operations/audience" element={<PlaceholderPage title="Audience Manager" description="Segment and manage your contact audiences here." />} />
        {/* Developers */}
        <Route path="/developer/api-key" element={<PlaceholderPage title="API Key" description="Manage your API keys for programmatic access to MindoraXai." />} />
        <Route path="/developer/webhooks" element={<PlaceholderPage title="Webhooks" description="Configure inbound and outbound webhook endpoints." />} />
        <Route path="/developer/logs" element={<PlaceholderPage title="Logs" description="Live request and event logs for your integration." />} />
        <Route path="/developer/code-mode" element={<PlaceholderPage title="Code Mode" description="Write and test custom bot logic with full code access." />} />
        {/* Billing */}
        <Route path="/billing" element={<PlaceholderPage title="Current Plan" description="View and manage your MindoraXai subscription and usage." />} />
        <Route path="/legal/:doc" element={<PortalStaticDoc variant="legal" />} />
        <Route path="/help" element={<PortalStaticDoc variant="help" />} />
        <Route path="/login" element={<Navigate to="/dashboard" replace />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}
