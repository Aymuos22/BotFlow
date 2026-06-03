/**
 * Admin inbox viewer — lets an admin pick any company and browse its WhatsApp inbox.
 * Reuses the same CompanyInbox component that portal users see.
 */
import { useEffect, useState } from "react";
import { listCompanies, type CompanySummary } from "../lib/api";
import CompanyInbox from "./CompanyInbox";
import { PageLoader, Spinner } from "../components/Spinner";

type Props = {
  accessToken: string;
};

export default function AdminInbox({ accessToken }: Props) {
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listCompanies(accessToken)
      .then((data) => {
        const active = data.filter((c) => c.status === "active");
        setCompanies(active.length > 0 ? active : data);
        if (data.length > 0) setSelectedCompanyId(data[0].id);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load companies"))
      .finally(() => setLoading(false));
  }, [accessToken]);

  if (loading) return <PageLoader message="Loading companies…" />;

  if (err) {
    return (
      <div style={{ padding: "2rem" }}>
        <p className="error">{err}</p>
      </div>
    );
  }

  if (companies.length === 0) {
    return (
      <div style={{ padding: "2rem" }}>
        <p>No companies found.</p>
      </div>
    );
  }

  const selected = companies.find((c) => c.id === selectedCompanyId);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "var(--text-secondary)" }}>
          Viewing inbox for:
        </span>
        <select
          value={selectedCompanyId ?? ""}
          onChange={(e) => setSelectedCompanyId(e.target.value || null)}
          style={{
            padding: "0.4rem 0.75rem",
            borderRadius: "8px",
            border: "1px solid var(--wa-border)",
            background: "var(--wa-bg)",
            color: "var(--text-primary)",
            fontSize: "0.95rem",
            cursor: "pointer",
          }}
        >
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.display_name || c.name} ({c.status})
            </option>
          ))}
        </select>
        {selected && (
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            ID: {selected.id}
          </span>
        )}
      </div>

      {selectedCompanyId ? (
        <CompanyInbox
          key={selectedCompanyId}
          accessToken={accessToken}
          companyId={selectedCompanyId}
        />
      ) : (
        <p style={{ color: "var(--text-secondary)" }}>Select a company above.</p>
      )}
    </div>
  );
}
