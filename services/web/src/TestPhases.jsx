// Each phase of a run going on, big (R5.5.3; owner, 15 Nov 2026: "How many have run and how many are left in this
// phase"; "Make it big and fat on screen"): done, about how many left, the phase running now highlighted.
export function Phases({ phases }) {
  if (!phases || !phases.length) return null;
  const now = phases.find((x) => x.state === "running");
  return (
    <div className="test-phases" aria-live="polite">
      {now && (
        <div className="test-phase-now">
          <span className="label">Now: {now.name}</span>
          <span className="big">{now.done}</span>
          <span className="of">{now.total != null ? <>done · <b>{now.left}</b> left of about {now.total}</> : "done so far (first run of this phase: how many are left is not known yet)"}</span>
          {now.total != null && <div className="test-progress-bar big"><span style={{ width: `${now.percent}%` }} /></div>}
        </div>)}
      <div className="test-phase-row">
        {phases.map((x) => (
          <div key={x.suite} className={`test-phase ${x.state}`}>
            <span className="name">{x.name}</span>
            <span className="count">{x.done}{x.total != null ? <small> / {x.total}</small> : null}</span>
            <span className="small">{x.state === "running" ? (x.left != null ? `${x.left} left` : "running") : x.state === "finished" ? "done" : x.state}</span>
          </div>))}
      </div>
    </div>
  );
}
