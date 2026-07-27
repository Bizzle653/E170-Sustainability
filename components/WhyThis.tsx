export type PriorityMatch = { key: string; label: string; matched: boolean; profile_weight: number };
export type EsgField = { key: string; label: string; raw_value: number };
export type AlignmentDetail = {
  explanation: string;
  priority_breakdown: PriorityMatch[];
  esg_snapshot: EsgField[];
};

function Toggle({open, onToggle}: {open: boolean; onToggle: () => void}) {
  return (
    <button className="whyToggle" onClick={onToggle} aria-expanded={open}>
      {open ? "Hide details −" : "Why this? +"}
    </button>
  );
}

function Panel({detail}: {detail: AlignmentDetail}) {
  return (
    <div className="whyDetail">
      <p>{detail.explanation}</p>
      {detail.priority_breakdown.length > 0 && (
        <div className="priorityChecklist">
          {detail.priority_breakdown.map((item) => (
            <span className={item.matched ? "matched" : "unmatched"} key={item.key}>
              {item.matched ? "✓" : "✗"} {item.label}
            </span>
          ))}
        </div>
      )}
      {detail.esg_snapshot.length > 0 && (
        <div className="esgSnapshotList">
          {detail.esg_snapshot.map((field) => (
            <span key={field.key}>
              <b>{field.label}:</b> {field.raw_value.toFixed(1)} <small>(lower is better)</small>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export const WhyThis = {Toggle, Panel};
