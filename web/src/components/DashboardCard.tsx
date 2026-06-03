type Props = {
  label: string;
  value: string;
  helper?: string;
  trend?: string;
};

export default function DashboardCard({ label, value, helper, trend }: Props) {
  const positive = trend?.trim().startsWith("+");
  const negative = trend?.trim().startsWith("-");

  return (
    <section className="dashboard-card">
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
      {(helper || trend) && (
        <footer>
          {trend && (
            <span className={positive ? "trend trend--up" : negative ? "trend trend--down" : "trend"}>
              {trend}
            </span>
          )}
          {helper && <span>{helper}</span>}
        </footer>
      )}
    </section>
  );
}
