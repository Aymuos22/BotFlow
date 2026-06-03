export type ActivityRow = {
  label: string;
  detail: string;
  value: string;
  time?: string;
};

type Props = {
  rows: ActivityRow[];
};

export default function RecentActivityTable({ rows }: Props) {
  return (
    <section className="recent-activity">
      <header>
        <h3>Recent Activity</h3>
      </header>
      {rows.length === 0 ? (
        <div className="chart-empty">No recent activity yet.</div>
      ) : (
        <div className="table-scroll">
          <table className="companies">
            <thead>
              <tr>
                <th>Activity</th>
                <th>Detail</th>
                <th>Count</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${row.label}-${idx}`}>
                  <td style={{ fontWeight: 700 }}>{row.label}</td>
                  <td>{row.detail}</td>
                  <td>{row.value}</td>
                  <td>{row.time || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
