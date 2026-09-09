import { FormEvent, useState } from "react";
import { supabase } from "../lib/supabase";
import { portalLogin, type PortalLoginResponse } from "../lib/api";
import { useToast } from "../context/ToastContext";
import ThemeToggle from "../components/ThemeToggle";
type Props = {
  onPortalLogin: (session: PortalLoginResponse) => void;
};

export default function Login({ onPortalLogin }: Props) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const portalSession = await portalLogin(email.trim(), password);
      onPortalLogin(portalSession);
      toast.success("Signed in.");
      return;
    } catch {
      // Fall back to Supabase for legacy accounts that are not DB-backed portal users.
    }
    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setBusy(false);
    if (!error) {
      toast.success("Signed in.");
      return;
    }
    const msg =
      error.status === 400 || error.message.toLowerCase().includes("invalid")
        ? "Incorrect username/email or password. Please try again."
        : error.message;
    setErr(msg);
    toast.error(msg);
  }

  async function onForgotPassword() {
    const loginId = email.trim();
    setErr(null);
    if (!loginId) {
      const msg = "Enter your username or email first.";
      setErr(msg);
      toast.error(msg);
      return;
    }
    if (!loginId.includes("@")) {
      const msg =
        "For username accounts, ask your portal admin to reset your password from Admin -> Portal users.";
      setErr(msg);
      toast.info(msg);
      return;
    }
    setResetBusy(true);
    const { error } = await supabase.auth.resetPasswordForEmail(loginId, {
      redirectTo: window.location.origin,
    });
    setResetBusy(false);
    if (error) {
      setErr(error.message);
      toast.error(error.message);
      return;
    }
    toast.success("Password reset email sent.");
  }

  return (
    <div className="auth-page">
      <div className="auth-toolbar">
        <ThemeToggle />
      </div>
      <div className="auth-card stack">
        <div className="auth-brand">
          <svg viewBox="0 0 36 32" fill="none" aria-hidden style={{ width: 40, height: 36, color: "var(--accent, #6366f1)" }}>
            <rect x="1" y="1" width="34" height="24" rx="6" stroke="currentColor" strokeWidth="2" opacity="0.8" />
            <circle cx="10" cy="13" r="2.5" fill="currentColor" />
            <circle cx="18" cy="13" r="2.5" fill="currentColor" />
            <circle cx="26" cy="13" r="2.5" fill="currentColor" />
            <path d="M11 25 L14 31 L17 25" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="none" />
          </svg>
          <div>
            <strong>BotFlow</strong>
            <span>Admin Portal</span>
          </div>
        </div>
        <div className="auth-heading">
          <h1>Welcome back</h1>
          <p className="lead">Sign in to continue.</p>
        </div>
        <form className="stack" onSubmit={onSubmit}>
          <label>
            <span>Username or email</span>
            <input
              type="text"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="company_user or you@example.com"
            />
          </label>
          <label>
            <span>Password</span>
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
              />
              <button
                type="button"
                className="secondary password-field__toggle"
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>
          {err && <p className="error">{err}</p>}
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => setForgotOpen((v) => !v)}
          >
            Forgot password?
          </button>
          {forgotOpen && (
            <div className="card" style={{ padding: "1rem" }}>
              <p className="lead" style={{ marginTop: 0 }}>
                Enter your username or email above, then continue.
              </p>
              <button
                type="button"
                className="secondary"
                disabled={resetBusy}
                onClick={() => void onForgotPassword()}
              >
                {resetBusy ? "Sending..." : "Reset password"}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
