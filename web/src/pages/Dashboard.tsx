import { useEffect, useMemo, useState } from "react";
import { listCompanies, type CompanySummary } from "../lib/api";
import {
  analyticsLanguages,
  analyticsLeads,
  analyticsOverview,
  analyticsTopQueries,
  getProductAnalytics,
  listInboxConversations,
  listPortalUsers,
  type LeadWarmthAnalytics,
  type PortalUser,
  type ProductAnalyticsResponse,
} from "../lib/supportApi";
import DashboardCard from "../components/DashboardCard";
import AnalyticsChart from "../components/AnalyticsChart";
import RecentActivityTable, { type ActivityRow } from "../components/RecentActivityTable";
import { PageLoader } from "../components/Spinner";

type Overview = {
  total_customer_messages: number;
  total_bot_messages: number;
  total_fallback_messages: number;
  total_handoffs: number;
  active_conversations: number;
  fallback_rate: number;
  handoff_rate: number;
};

type LanguageResponse = {
  breakdown: Array<{ language: string; count: number; percentage: number }>;
};

type TopQueriesResponse = {
  top_queries: Array<{ query: string; count: number; last_seen?: string | null }>;
};

type Props = {
  accessToken: string;
  role: "admin" | "user";
  companyId: string | null;
};

const PERIOD_DAYS = 30;

type ProductInsightRow = {
  key: string;
  name: string;
  product: string;
  company: string;
  inquired: number;
  suggested: number;
  conversations: number;
  rate: number;
};

function asOverview(value: unknown): Overview {
  const v = (value || {}) as Partial<Overview>;
  return {
    total_customer_messages: Number(v.total_customer_messages || 0),
    total_bot_messages: Number(v.total_bot_messages || 0),
    total_fallback_messages: Number(v.total_fallback_messages || 0),
    total_handoffs: Number(v.total_handoffs || 0),
    active_conversations: Number(v.active_conversations || 0),
    fallback_rate: Number(v.fallback_rate || 0),
    handoff_rate: Number(v.handoff_rate || 0),
  };
}

function pct(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

function numberFmt(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

function isRelevantQuery(query: string): boolean {
  const normalized = query.trim().toLowerCase().replace(/[?!.,\s]+/g, " ");
  if (normalized.length < 4) return false;
  const ignored = new Set([
    "hi",
    "hii",
    "hello",
    "hey",
    "yes",
    "no",
    "ok",
    "okay",
    "done",
    "thanks",
    "thank you",
    "good morning",
    "good afternoon",
    "good evening",
  ]);
  return !ignored.has(normalized);
}

function growth(current: number, previous: number): string {
  if (previous <= 0) return current > 0 ? "+100%" : "0%";
  const delta = ((current - previous) / previous) * 100;
  return `${delta >= 0 ? "+" : ""}${Math.round(delta * 10) / 10}%`;
}

function combineOverview(items: Overview[]): Overview {
  const total = items.reduce(
    (acc, item) => ({
      total_customer_messages: acc.total_customer_messages + item.total_customer_messages,
      total_bot_messages: acc.total_bot_messages + item.total_bot_messages,
      total_fallback_messages: acc.total_fallback_messages + item.total_fallback_messages,
      total_handoffs: acc.total_handoffs + item.total_handoffs,
      active_conversations: acc.active_conversations + item.active_conversations,
      fallback_rate: 0,
      handoff_rate: 0,
    }),
    {
      total_customer_messages: 0,
      total_bot_messages: 0,
      total_fallback_messages: 0,
      total_handoffs: 0,
      active_conversations: 0,
      fallback_rate: 0,
      handoff_rate: 0,
    },
  );
  total.fallback_rate =
    total.total_bot_messages > 0 ? total.total_fallback_messages / total.total_bot_messages : 0;
  total.handoff_rate =
    total.total_customer_messages > 0 ? total.total_handoffs / total.total_customer_messages : 0;
  return total;
}

export default function Dashboard({ accessToken, role, companyId }: Props) {
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [users, setUsers] = useState<PortalUser[]>([]);
  const [overview, setOverview] = useState<Overview>(combineOverview([]));
  const [previousOverview, setPreviousOverview] = useState<Overview>(combineOverview([]));
  const [leadSeries, setLeadSeries] = useState<Record<string, unknown>[]>([]);
  const [languageData, setLanguageData] = useState<Record<string, unknown>[]>([]);
  const [messageBars, setMessageBars] = useState<Record<string, unknown>[]>([]);
  const [activityRows, setActivityRows] = useState<ActivityRow[]>([]);
  const [productSeries, setProductSeries] = useState<Record<string, unknown>[]>([]);
  const [topInquiredProducts, setTopInquiredProducts] = useState<ProductInsightRow[]>([]);
  const [topSuggestedProducts, setTopSuggestedProducts] = useState<ProductInsightRow[]>([]);

  useEffect(() => {
    let alive = true;
    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const companyList =
          role === "admin"
            ? await listCompanies(accessToken)
            : companyId
              ? []
              : [];
        const scopedCompanies =
          role === "admin"
            ? companyList
            : companyId
              ? [{ id: companyId, name: "Assigned company", display_name: "Assigned company", status: "active" }]
              : [];
        const userList = role === "admin" ? await listPortalUsers(accessToken) : [];
        const targetCompanies = scopedCompanies.slice(0, 12);

        const analytics = await Promise.all(
          targetCompanies.map(async (company) => {
            const [currentRaw, previousRaw, languagesRaw, leadsRaw, topRaw, inboxRaw, productsRaw] =
              await Promise.all([
                analyticsOverview(accessToken, company.id, PERIOD_DAYS).catch(() => null),
                analyticsOverview(accessToken, company.id, PERIOD_DAYS * 2).catch(() => null),
                analyticsLanguages(accessToken, company.id, PERIOD_DAYS).catch(() => null),
                analyticsLeads(accessToken, company.id, PERIOD_DAYS).catch(() => null),
                analyticsTopQueries(accessToken, company.id, PERIOD_DAYS).catch(() => null),
                listInboxConversations(accessToken, company.id).catch(() => []),
                getProductAnalytics(accessToken, company.id, PERIOD_DAYS, 50).catch(() => null),
              ]);
            const current = asOverview(currentRaw);
            const sixty = asOverview(previousRaw);
            return {
              company,
              current,
              previous: {
                ...sixty,
                total_customer_messages: Math.max(
                  0,
                  sixty.total_customer_messages - current.total_customer_messages,
                ),
              },
              languages: (languagesRaw as LanguageResponse | null)?.breakdown ?? [],
              leads: leadsRaw as LeadWarmthAnalytics | null,
              topQueries: (topRaw as TopQueriesResponse | null)?.top_queries ?? [],
              inboxCount: Array.isArray(inboxRaw) ? inboxRaw.length : 0,
              products: productsRaw as ProductAnalyticsResponse | null,
            };
          }),
        );

        const combined = combineOverview(analytics.map((item) => item.current));
        const previous = combineOverview(analytics.map((item) => item.previous));
        const langMap = new Map<string, number>();
        analytics.forEach((item) => {
          item.languages.forEach((lang) => {
            langMap.set(lang.language || "unknown", (langMap.get(lang.language || "unknown") || 0) + lang.count);
          });
        });
        const leadsByDate = new Map<string, { date: string; hot: number; warm: number; cold: number }>();
        analytics.forEach((item) => {
          item.leads?.series.forEach((point) => {
            const existing = leadsByDate.get(point.date) || { date: point.date, hot: 0, warm: 0, cold: 0 };
            existing.hot += point.hot;
            existing.warm += point.warm;
            existing.cold += point.cold;
            leadsByDate.set(point.date, existing);
          });
        });
        const activities = analytics
          .flatMap((item) =>
            item.topQueries
              .filter((q) => isRelevantQuery(q.query))
              .slice(0, 4)
              .map((q) => ({
                label: item.company.display_name || item.company.name,
                detail: q.query,
                value: numberFmt(q.count),
                time: q.last_seen || undefined,
              })),
          )
          .slice(0, 8);
        const productRows: ProductInsightRow[] = analytics
          .flatMap((item) => {
            const companyName = item.company.display_name || item.company.name;
            return (item.products?.items ?? []).map((p) => ({
              key: `${item.company.id}:${p.product_id}`,
              name: p.sku || p.name,
              product: p.name,
              company: companyName,
              inquired: p.retrieved_count,
              suggested: p.suggested_count,
              conversations: p.unique_conversations,
              rate: p.suggestion_rate_pct,
            }));
          })
          .sort((a, b) => (b.inquired + b.suggested) - (a.inquired + a.suggested));
        const productSeriesByDate = new Map<string, { date: string; inquired: number; suggested: number }>();
        analytics.forEach((item) => {
          item.products?.series.forEach((point) => {
            const existing = productSeriesByDate.get(point.date) || {
              date: point.date,
              inquired: 0,
              suggested: 0,
            };
            existing.inquired += point.retrieved_count;
            existing.suggested += point.suggested_count;
            productSeriesByDate.set(point.date, existing);
          });
        });

        if (!alive) return;
        setCompanies(companyList);
        setUsers(userList);
        setOverview(combined);
        setPreviousOverview(previous);
        setLanguageData(
          Array.from(langMap.entries()).map(([name, count]) => ({ name, count })),
        );
        setLeadSeries(Array.from(leadsByDate.values()).sort((a, b) => a.date.localeCompare(b.date)));
        setMessageBars(
          analytics.map((item) => ({
            name: item.company.display_name || item.company.name,
            customer: item.current.total_customer_messages,
            bot: item.current.total_bot_messages,
            fallbacks: item.current.total_fallback_messages,
            inbox: item.inboxCount,
          })),
        );
        setActivityRows(activities);
        setProductSeries(
          Array.from(productSeriesByDate.values()).sort((a, b) =>
            a.date.localeCompare(b.date),
          ),
        );
        setTopInquiredProducts(
          [...productRows]
            .sort((a, b) => b.inquired - a.inquired)
            .filter((item) => item.inquired > 0)
            .slice(0, 10),
        );
        setTopSuggestedProducts(
          [...productRows]
            .sort((a, b) => b.suggested - a.suggested)
            .filter((item) => item.suggested > 0)
            .slice(0, 10),
        );
      } catch (e) {
        if (!alive) return;
        setErr(e instanceof Error ? e.message : "Failed to load dashboard");
      } finally {
        if (alive) setLoading(false);
      }
    }
    void load();
    return () => {
      alive = false;
    };
  }, [accessToken, role, companyId]);

  const activeCompanies = useMemo(
    () => companies.filter((c) => c.status.toLowerCase() === "active").length,
    [companies],
  );

  if (loading) {
    return (
      <div className="dashboard-page">
        <PageLoader message="Loading dashboard..." />
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <p>Live overview</p>
          <h1>Dashboard</h1>
          <span>Real analytics from the last {PERIOD_DAYS} days.</span>
        </div>
      </section>

      {err && <p className="error">{err}</p>}

      <div className="dashboard-card-grid">
        <DashboardCard
          label="Customer messages"
          value={numberFmt(overview.total_customer_messages)}
          trend={growth(overview.total_customer_messages, previousOverview.total_customer_messages)}
          helper={`vs previous ${PERIOD_DAYS} days`}
        />
        <DashboardCard
          label="Bot replies"
          value={numberFmt(overview.total_bot_messages)}
          helper={`${pct(overview.fallback_rate)} fallback rate`}
        />
        <DashboardCard
          label="Handoffs"
          value={numberFmt(overview.total_handoffs)}
          helper={`${pct(overview.handoff_rate)} handoff rate`}
        />
        <DashboardCard
          label={role === "admin" ? "Portal users" : "Active conversations"}
          value={role === "admin" ? numberFmt(users.length) : numberFmt(overview.active_conversations)}
          helper={role === "admin" ? `${activeCompanies} active companies` : "Current company"}
        />
      </div>

      <div className="dashboard-chart-grid">
        <AnalyticsChart
          title="Lead Warmth Trend"
          subtitle="Hot, warm, and cold leads over time"
          kind="line"
          data={leadSeries}
          xKey="date"
          series={["hot", "warm", "cold"]}
        />
        <AnalyticsChart
          title="Message Volume"
          subtitle="Customer and bot messages by company"
          kind="bar"
          data={messageBars}
          xKey="name"
          series={["customer", "bot", "fallbacks"]}
        />
        <AnalyticsChart
          title="Language Mix"
          subtitle="Detected customer language distribution"
          kind="donut"
          data={languageData}
          xKey="name"
          series={["count"]}
        />
        <AnalyticsChart
          title="Product Interest"
          subtitle="Daily customer inquiries and bot product suggestions"
          kind="line"
          data={productSeries}
          xKey="date"
          series={["inquired", "suggested"]}
        />
      </div>

      <section className="recent-activity">
        <header>
          <div>
            <h3>Product Breakdown</h3>
            <p>Top products from the last {PERIOD_DAYS} days.</p>
          </div>
        </header>
        {topInquiredProducts.length === 0 && topSuggestedProducts.length === 0 ? (
          <div className="chart-empty">No product analytics yet.</div>
        ) : (
          <div className="grid-responsive" style={{ gap: "1rem" }}>
            <div>
              <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem", fontWeight: 700 }}>
                Customers inquired about
              </h4>
              <div className="table-scroll">
                <table className="companies" style={{ fontSize: "0.82rem" }}>
                  <thead>
                    <tr>
                      <th>Product</th>
                      {role === "admin" ? <th>Company</th> : null}
                      <th>Inquiries</th>
                      <th>Convs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topInquiredProducts.map((item) => (
                      <tr key={item.key}>
                        <td>{item.product}</td>
                        {role === "admin" ? <td>{item.company}</td> : null}
                        <td style={{ fontWeight: 700 }}>{item.inquired}</td>
                        <td>{item.conversations}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.9rem", fontWeight: 700 }}>
                Bot suggested
              </h4>
              <div className="table-scroll">
                <table className="companies" style={{ fontSize: "0.82rem" }}>
                  <thead>
                    <tr>
                      <th>Product</th>
                      {role === "admin" ? <th>Company</th> : null}
                      <th>Suggested</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topSuggestedProducts.map((item) => (
                      <tr key={item.key}>
                        <td>{item.product}</td>
                        {role === "admin" ? <td>{item.company}</td> : null}
                        <td style={{ fontWeight: 700 }}>{item.suggested}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </section>

      <RecentActivityTable rows={activityRows} />
    </div>
  );
}
