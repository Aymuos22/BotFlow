import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

type ChartKind = "line" | "bar" | "donut";

type Props = {
  title: string;
  subtitle?: string;
  kind: ChartKind;
  data: Record<string, unknown>[];
  xKey?: string;
  series: string[];
};

export default function AnalyticsChart({ title, subtitle, kind, data, xKey = "name", series }: Props) {
  const empty = data.length === 0;

  return (
    <section className="analytics-chart">
      <header>
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </header>
      {empty ? (
        <div className="chart-empty">No data available yet.</div>
      ) : (
        <div className="chart-frame">
          <ResponsiveContainer width="100%" height="100%">
            {kind === "line" ? (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey={xKey} tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis tickLine={false} axisLine={false} width={40} />
                <Tooltip />
                <Legend />
                {series.map((key, idx) => (
                  <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2.4} dot={false} />
                ))}
              </LineChart>
            ) : kind === "bar" ? (
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey={xKey} tickLine={false} axisLine={false} minTickGap={18} />
                <YAxis tickLine={false} axisLine={false} width={40} />
                <Tooltip />
                <Legend />
                {series.map((key, idx) => (
                  <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} radius={[6, 6, 0, 0]} />
                ))}
              </BarChart>
            ) : (
              <PieChart>
                <Tooltip />
                <Legend />
                <Pie data={data} dataKey={series[0]} nameKey={xKey} innerRadius={54} outerRadius={86} paddingAngle={3}>
                  {data.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
