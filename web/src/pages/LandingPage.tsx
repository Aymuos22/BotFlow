import { useNavigate } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import brandLogo from "../../logo/logo.jpeg";

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="landing-root">
      {/* ── Top Navbar ─────────────────────────────────────────────────────── */}
      <header className="landing-nav">
        <div className="landing-nav__inner">
          <div className="landing-nav__brand">
            <img src={brandLogo} alt="MindoraXai logo" className="landing-nav__logo" />
            <span className="landing-nav__name">MindoraXai</span>
          </div>
          <nav className="landing-nav__links">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <ThemeToggle />
            <button
              className="landing-btn-primary"
              onClick={() => navigate("/login")}
            >
              Login
            </button>
          </nav>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="landing-hero">
        <div className="landing-hero__glow landing-hero__glow--left" />
        <div className="landing-hero__glow landing-hero__glow--right" />
        <div className="landing-hero__content">
          <div className="landing-badge">AI-Powered WhatsApp Platform</div>
          <h1 className="landing-hero__headline">
            Turn every conversation<br />
            into a <span className="landing-accent">customer</span>
          </h1>
          <p className="landing-hero__sub">
            MindoraXai brings intelligent AI agents, lead management, WhatsApp
            campaigns, and real-time analytics into one unified portal — built
            for teams that move fast.
          </p>
          <div className="landing-hero__actions">
            <button
              className="landing-btn-primary landing-btn-lg"
              onClick={() => navigate("/login")}
            >
              Get started &rarr;
            </button>
            <a href="#features" className="landing-btn-ghost landing-btn-lg">
              See features
            </a>
          </div>
        </div>

        {/* Floating dashboard preview card */}
        <div className="landing-hero__preview" aria-hidden>
          <div className="landing-preview-card">
            <div className="landing-preview-card__header">
              <span className="landing-preview-dot landing-preview-dot--red" />
              <span className="landing-preview-dot landing-preview-dot--yellow" />
              <span className="landing-preview-dot landing-preview-dot--green" />
              <span className="landing-preview-card__title">MindoraXai Portal</span>
            </div>
            <div className="landing-preview-card__body">
              <div className="landing-stat-row">
                <div className="landing-stat">
                  <span className="landing-stat__value">2,847</span>
                  <span className="landing-stat__label">Conversations</span>
                </div>
                <div className="landing-stat">
                  <span className="landing-stat__value">94%</span>
                  <span className="landing-stat__label">Resolution rate</span>
                </div>
                <div className="landing-stat">
                  <span className="landing-stat__value">1.2s</span>
                  <span className="landing-stat__label">Avg. response</span>
                </div>
              </div>
              <div className="landing-chat-preview">
                <div className="landing-chat-msg landing-chat-msg--in">
                  Hi, what are your delivery charges?
                </div>
                <div className="landing-chat-msg landing-chat-msg--out">
                  Delivery is free on orders above ₹499 🎉
                </div>
                <div className="landing-chat-msg landing-chat-msg--in">
                  Great! How do I place an order?
                </div>
                <div className="landing-chat-msg landing-chat-msg--out landing-chat-msg--typing">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────────────────── */}
      <section className="landing-section" id="features">
        <div className="landing-section__inner">
          <div className="landing-section__label">Features</div>
          <h2 className="landing-section__title">Everything your team needs</h2>
          <p className="landing-section__sub">
            One platform for AI conversations, campaigns, lead pipelines, and analytics.
          </p>
          <div className="landing-features-grid">
            {FEATURES.map((f) => (
              <div className="landing-feature-card" key={f.title}>
                <div className="landing-feature-card__icon">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────────────────── */}
      <section className="landing-section landing-section--alt" id="how-it-works">
        <div className="landing-section__inner">
          <div className="landing-section__label">How it works</div>
          <h2 className="landing-section__title">Up and running in minutes</h2>
          <div className="landing-steps">
            {STEPS.map((s, i) => (
              <div className="landing-step" key={s.title}>
                <div className="landing-step__num">{i + 1}</div>
                <div>
                  <h3>{s.title}</h3>
                  <p>{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ──────────────────────────────────────────────────────── */}
      <section className="landing-cta">
        <div className="landing-cta__inner">
          <h2>Ready to automate your customer conversations?</h2>
          <p>Log in to your portal and deploy your first AI agent today.</p>
          <button
            className="landing-btn-primary landing-btn-lg"
            onClick={() => navigate("/login")}
          >
            Login to your portal
          </button>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="landing-footer__inner">
          <div className="landing-footer__brand">
            <img src={brandLogo} alt="MindoraXai" className="landing-nav__logo" />
            <span>MindoraXai</span>
          </div>
          <p className="landing-footer__copy">
            &copy; {new Date().getFullYear()} MindoraXai. All rights reserved.
          </p>
          <div className="landing-footer__links">
            <a href="/legal/privacy">Privacy</a>
            <a href="/legal/terms">Terms</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

// ── Static data ───────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
        <path d="M8 10h8M8 14h5" />
      </svg>
    ),
    title: "AI Chat Agent",
    desc: "Deploy a GPT-powered agent that answers customer questions 24/7 with your own knowledge base and catalog.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-6l-2 3h-4l-2-3H2" />
        <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
      </svg>
    ),
    title: "Conversation Inbox",
    desc: "Full conversation history, lead warmth scoring, and one-click human handoff for agents managing live chats.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 11v2a2 2 0 0 0 2 2h3" />
        <path d="M7 13V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v8" />
        <path d="M7 21h10a2 2 0 0 0 2-2v-4H5v4a2 2 0 0 0 2 2z" />
      </svg>
    ),
    title: "WhatsApp Campaigns",
    desc: "Send bulk WhatsApp campaigns with approved templates, target audiences, and live delivery tracking.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" />
        <path d="M7 12v5M12 7v10M17 9v8" />
      </svg>
    ),
    title: "Analytics Dashboard",
    desc: "Track message volume, handoff rates, lead conversion, and agent performance with real-time charts.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    title: "Follow-up Automation",
    desc: "Automatically re-engage warm leads with timed follow-up messages so no opportunity is missed.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6M8 13h8M8 17h8" />
      </svg>
    ),
    title: "Google Sheets Sync",
    desc: "Export leads and conversation data to Google Sheets automatically, keeping your CRM always in sync.",
  },
];

const STEPS = [
  {
    title: "Connect your WhatsApp number",
    desc: "Link your Meta or AiSensy account in minutes. No code required — just your API credentials.",
  },
  {
    title: "Upload your knowledge base",
    desc: "Add product catalogs, FAQs, and policies. The AI agent learns from your documents instantly.",
  },
  {
    title: "Deploy and monitor",
    desc: "Go live and watch the dashboard. Fine-tune handoff rules, campaigns, and automations from the portal.",
  },
];
