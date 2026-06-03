import { useCallback, useEffect, useState } from "react";
import {
  createFollowupRule,
  deleteFollowupRule,
  listFollowupRules,
  listOutboxJobs,
  updateFollowupRule,
  type FollowupRule,
  type OutboxJob,
} from "../lib/supportApi";
import FollowupTemplatePicker, {
  parseFollowupBodyVariablesCsv,
} from "../components/FollowupTemplatePicker";
import { PageLoader } from "../components/Spinner";
import { useToast } from "../context/ToastContext";

type Props = {
  accessToken: string;
  companyId: string;
};

export default function CompanyFollowups({ accessToken, companyId }: Props) {
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [followupRules, setFollowupRules] = useState<FollowupRule[]>([]);
  const [outboxJobs, setOutboxJobs] = useState<OutboxJob[]>([]);
  const [followupName, setFollowupName] = useState("Open lead reminder");
  const [followupDelay, setFollowupDelay] = useState(1440);
  const [followupTemplate, setFollowupTemplate] = useState("");
  const [followupLang, setFollowupLang] = useState("en");
  const [followupBodyVarsCsv, setFollowupBodyVarsCsv] = useState("");

  const refresh = useCallback(async () => {
    const [rules, jobs] = await Promise.all([
      listFollowupRules(accessToken, companyId),
      listOutboxJobs(accessToken, companyId, {}),
    ]);
    setFollowupRules(rules);
    setOutboxJobs(jobs);
  }, [accessToken, companyId]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        await refresh();
      } catch (e) {
        if (!cancel) {
          toast.error(e instanceof Error ? e.message : "Failed to load follow-ups");
        }
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [refresh, toast]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="inbox-page">
        <PageLoader message="Loading follow-ups…" />
      </div>
    );
  }

  return (
    <div className="inbox-page" style={{ maxWidth: 1100 }}>
      <header style={{ marginBottom: "1.25rem" }}>
        <h1 style={{ margin: 0, fontSize: "1.35rem", fontWeight: 800 }}>Open-lead follow-ups</h1>
        <p className="lead" style={{ margin: "0.35rem 0 0", color: "var(--text-muted)", maxWidth: 720 }}>
          Configure which <strong>approved Meta template</strong> is used after the messaging window closes (preview loads from Meta).
          While the chat is still open (~24h), an <strong>AI-written</strong> message is sent instead. Mark{" "}
          <strong>inquiry complete</strong> in Inbox to stop automated follow-ups for that thread.
        </p>
        <p style={{ margin: "0.75rem 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
          While the WhatsApp conversation is still typically open (within about <strong>24 hours</strong> of the customer&apos;s
          last message), follow-ups send as one <strong>AI-written</strong> message using your company&apos;s outbound WhatsApp
          provider (Meta, Twilio, or AiSensy). After that window, WhatsApp expects an approved <strong>Meta template</strong> —
          the worker uses the rule&apos;s template name. Configure Meta plus LLM/API keys appropriately.
          The server outbox worker must be running.
        </p>
      </header>

      <div className="grid-responsive" style={{ gap: "1rem", alignItems: "start" }}>
        <div className="support-card compact">
          <h2 className="support-subhead" style={{ marginTop: 0 }}>
            Create rule
          </h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <label>
              <span>Rule name</span>
              <input
                value={followupName}
                onChange={(e) => setFollowupName(e.target.value)}
                placeholder="Open lead reminder"
              />
            </label>
            <label>
              <span>Delay (minutes)</span>
              <input
                type="number"
                min={1}
                value={followupDelay}
                onChange={(e) => setFollowupDelay(Number(e.target.value || 1))}
              />
            </label>
          </div>
          <FollowupTemplatePicker
            accessToken={accessToken}
            companyId={companyId}
            templateName={followupTemplate}
            setTemplateName={setFollowupTemplate}
            languageCode={followupLang}
            setLanguageCode={setFollowupLang}
            bodyVariablesCsv={followupBodyVarsCsv}
            setBodyVariablesCsv={setFollowupBodyVarsCsv}
          />
          <button
            type="button"
            className="primary"
            disabled={busy || !followupName.trim() || !followupTemplate.trim()}
            style={{ marginTop: "0.9rem" }}
            onClick={() => void run(async () => {
              await createFollowupRule(accessToken, companyId, {
                name: followupName.trim(),
                is_active: true,
                steps: [
                  {
                    delay_minutes: followupDelay,
                    template_name: followupTemplate.trim(),
                    language_code: followupLang.trim() || "en",
                    body_variables: parseFollowupBodyVariablesCsv(followupBodyVarsCsv),
                  },
                ],
              });
              toast.success("Follow-up rule created.");
              await refresh();
              setFollowupTemplate("");
              setFollowupBodyVarsCsv("");
            })}
          >
            Create follow-up rule
          </button>
        </div>

        <div className="support-card compact">
          <h2 className="support-subhead" style={{ marginTop: 0 }}>
            How it works
          </h2>
          <p style={{ marginTop: 0 }}>A rule sends after the configured delay from the customer&apos;s last message.</p>
          <p>
            It only applies when <code>inquiry_complete</code> is false.
          </p>
          <p>Outside the WhatsApp messaging window (~24 hours after last customer activity), sends use the Meta template instead of AI.</p>
          <p style={{ marginBottom: 0 }}>
            It is skipped if the customer replies again, sends an opt-out keyword, or the rule is paused.
          </p>
        </div>
      </div>

      <h2 className="support-subhead" style={{ marginTop: "1.5rem" }}>
        Follow-up rules
      </h2>
      <div className="table-scroll">
        <table className="companies">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Delay</th>
              <th>Template</th>
              <th>Active</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {followupRules.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ color: "var(--text-muted)" }}>
                  No follow-up rules yet.
                </td>
              </tr>
            ) : (
              followupRules.map((r) => {
                const firstStep = r.steps_json[0] || {};
                return (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{String(firstStep.delay_minutes ?? "-")} min</td>
                    <td>{String(firstStep.template_name ?? "-")}</td>
                    <td>{r.is_active ? "yes" : "no"}</td>
                    <td>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void run(async () => {
                          await updateFollowupRule(accessToken, companyId, r.id, { is_active: !r.is_active });
                          await refresh();
                        })}
                      >
                        {r.is_active ? "Pause" : "Enable"}
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        style={{ marginLeft: 6, color: "var(--danger)" }}
                        onClick={() => void run(async () => {
                          await deleteFollowupRule(accessToken, companyId, r.id);
                          await refresh();
                          toast.success("Rule deleted.");
                        })}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <h2 className="support-subhead">Recent follow-up outbox</h2>
      <div className="table-scroll table-scroll--wide">
        <table className="companies">
          <thead>
            <tr>
              <th>To</th>
              <th>Template</th>
              <th>Status</th>
              <th>Attempts</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {outboxJobs.filter((j) => j.kind === "followup").length === 0 ? (
              <tr>
                <td colSpan={5} style={{ color: "var(--text-muted)" }}>
                  No follow-up jobs yet (worker creates them when a lead is due).
                </td>
              </tr>
            ) : (
              outboxJobs
                .filter((j) => j.kind === "followup")
                .slice(0, 30)
                .map((j) => (
                  <tr key={j.id}>
                    <td>{j.to_number}</td>
                    <td>{j.template_name}</td>
                    <td>{j.status}</td>
                    <td>{j.attempts}</td>
                    <td style={{ maxWidth: 360 }}>{j.last_error || "—"}</td>
                  </tr>
                ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
