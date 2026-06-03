/** Accessible loading indicator — use with `.ui-spinner` styles in `index.css`. */
export function Spinner({
  size = "md",
  label = "Loading",
}: {
  size?: "sm" | "md" | "lg";
  label?: string;
}) {
  return (
    <span
      className={`ui-spinner ui-spinner--${size}`}
      role="status"
      aria-label={label}
    >
      <span className="ui-spinner__ring" aria-hidden />
    </span>
  );
}

export function PageLoader({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <Spinner size="lg" label={message} />
      <span className="page-loader__text">{message}</span>
    </div>
  );
}

/** Inline block for buttons / table rows */
export function InlineLoader({ label = "Loading" }: { label?: string }) {
  return (
    <span className="inline-loader" role="status" aria-label={label}>
      <Spinner size="sm" label={label} />
    </span>
  );
}
