export function Metric({
  label, value, note, hint, compare,
}: {
  label: string; value: string; note: string; hint?: string; compare?: string | null | false;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
      {compare && <small className="benchmarkNote">{compare}</small>}
      {/* Shown inline by default, not just on hover -- a hover-only tooltip is easy to
          miss entirely (and unusable on touch devices), which defeats the point for
          someone who doesn't already know what "volatility" or "drawdown" means. */}
      {hint && <small className="metricHint">{hint}</small>}
    </div>
  );
}
