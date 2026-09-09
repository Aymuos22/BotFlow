import { Link, Navigate, useParams } from "react-router-dom";

type DocBlock = {
  title: string;
  updated: string;
  sections: Array<{ heading: string; body: string[] }>;
};

const LEGAL_PAGES: Record<string, DocBlock> = {
  privacy: {
    title: "Privacy policy",
    updated: "Last updated: demonstration copy — replace with your counsel-approved policy.",
    sections: [
      {
        heading: "What we process",
        body: [
          "BotFlow processes messages, channel metadata, and configuration you submit so we can operate your assistant, inbox, and optional integrations (such as spreadsheets or WhatsApp templates).",
          "We minimise retention to what’s needed for support, debugging, analytics you enable, and legal obligations.",
        ],
      },
      {
        heading: "Your responsibilities",
        body: [
          "You are responsible for notices and lawful bases toward your customers, including WhatsApp commerce and marketing rules.",
          "Use the dashboard to honour access or deletion workflows your organisation adopts.",
        ],
      },
      {
        heading: "Contact",
        body: [
          "For privacy enquiries, contact your account administrator or the email shown under Contact (compliance) in the sidebar.",
        ],
      },
    ],
  },
  terms: {
    title: "Terms of service",
    updated: "Last updated: demonstration copy — replace with your legal terms.",
    sections: [
      {
        heading: "Using the portal",
        body: [
          "Accounts are provisioned per organisation. You agree not to abuse APIs, circumvent rate limits, or attempt unauthorised access to other tenants’ data.",
        ],
      },
      {
        heading: "Service availability",
        body: [
          "Features may evolve. Planned capabilities shown as “Soon” are not contractual commitments until released and documented.",
        ],
      },
      {
        heading: "Limitation",
        body: [
          "The platform is provided on an “as is” basis to the extent permitted by law — replace this section with your jurisdiction-specific wording.",
        ],
      },
    ],
  },
  cookies: {
    title: "Cookie & tracking notice",
    updated: "Last updated: demonstration copy.",
    sections: [
      {
        heading: "Session & preferences",
        body: [
          "The dashboard may store session tokens in your browser (for example portal or Supabase auth) and theme or UI preferences locally.",
        ],
      },
      {
        heading: "Analytics",
        body: [
          "If you enable product analytics, additional cookies or SDK identifiers may apply — document your vendor list here when connected.",
        ],
      },
    ],
  },
  security: {
    title: "Security overview",
    updated: "Last updated: demonstration copy.",
    sections: [
      {
        heading: "Controls",
        body: [
          "Transport is encrypted in transit (HTTPS). Secrets belong in environment configuration, not source control.",
          "Rotate API keys periodically and revoke access for former team members.",
        ],
      },
      {
        heading: "Incident response",
        body: [
          "Report suspected incidents through your administrator. Describe scope, timelines, and any customer impact.",
        ],
      },
    ],
  },
  accessibility: {
    title: "Accessibility statement",
    updated: "Last updated: demonstration copy.",
    sections: [
      {
        heading: "Commitment",
        body: [
          "We aim to meet WCAG 2.2 Level AA for core dashboard flows where feasible. Presentation-only or roadmap items may be incomplete.",
        ],
      },
      {
        heading: "Feedback",
        body: [
          "If you encounter a barrier, notify your administrator with the page, browser, and assistive technology in use.",
        ],
      },
    ],
  },
};

const HELP_DOC: DocBlock = {
  title: "Help center",
  updated: "Short answers for common dashboard tasks.",
  sections: [
    {
      heading: "Inbox & leads",
      body: [
        "Mark an inquiry complete to stop automated open-lead follow-ups for that conversation.",
        "Lead warmth labels are for prioritisation — they don’t trigger sends by themselves.",
      ],
    },
    {
      heading: "Follow-ups",
      body: [
        "Follow-ups use approved WhatsApp templates in Meta. Confirm template names and Meta credentials match production.",
      ],
    },
    {
      heading: "Need more?",
      body: ["Use Contact (compliance) in the sidebar for policy questions routed to your team."],
    },
  ],
};

export default function PortalStaticDoc({ variant }: { variant: "legal" | "help" }) {
  const params = useParams();
  if (variant === "help") {
    return renderDoc(HELP_DOC);
  }
  const key = (params.doc ?? "").toLowerCase();
  const cfg = LEGAL_PAGES[key];
  if (!cfg) {
    return <Navigate to="/dashboard" replace />;
  }
  return renderDoc(cfg);
}

function renderDoc(cfg: DocBlock) {
  return (
    <div className="inbox-page" style={{ maxWidth: 720 }}>
      <nav style={{ fontSize: "0.82rem", marginBottom: "0.75rem" }}>
        <Link to="/dashboard" style={{ fontWeight: 700 }}>
          ← Back to dashboard
        </Link>
      </nav>
      <h1 style={{ marginTop: 0, fontSize: "1.5rem", fontWeight: 800 }}>{cfg.title}</h1>
      <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginTop: "-0.25rem" }}>{cfg.updated}</p>
      {cfg.sections.map((s) => (
        <section key={s.heading} style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: "0.5rem" }}>{s.heading}</h2>
          {s.body.map((p, i) => (
            <p key={i} className="lead" style={{ margin: "0 0 0.65rem", lineHeight: 1.55 }}>
              {p}
            </p>
          ))}
        </section>
      ))}
    </div>
  );
}
