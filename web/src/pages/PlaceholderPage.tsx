type Props = { title: string; description?: string };

export default function PlaceholderPage({ title, description }: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        gap: "1rem",
        textAlign: "center",
        padding: "2rem",
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: "var(--accent-soft, #e8f0fe)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 28,
        }}
      >
        🔧
      </div>
      <h2 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 600 }}>{title}</h2>
      <p style={{ margin: 0, color: "var(--text-secondary)", maxWidth: 380 }}>
        {description ?? "This feature is being set up. Check back soon."}
      </p>
    </div>
  );
}
