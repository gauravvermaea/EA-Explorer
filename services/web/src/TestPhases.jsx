// Each phase of a run going on, big (R5.5.3; owner, 15 Nov 2026: "How many have run and how many are left in this
// phase"; "Make it big and fat on screen"): done, about how many left, the phase running now highlighted; and each
// area's passed and failed, so the area that is not working shows at once (R5.47).
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
          <div key={x.suite} className={`test-phase ${x.state}${x.failed ? " has-failed" : x.warning ? " has-warning" : ""}`}>
            <span className="name">{x.name}</span>
            <span className="count">{x.done}{x.total != null ? <small> / {x.total}</small> : null}</span>
            <span className="small">{x.state === "running" ? (x.left != null ? `${x.left} left` : "running") : x.state === "finished" ? "done" : x.state}</span>
            {x.done > 0 && (
              <span className="phase-outcomes" aria-label={`${x.name}: ${x.passed} passed, ${x.failed} failed`}>
                <span className="ok-text">{"\u2713"} {x.passed} passed</span>
                <span className={x.failed ? "bad-text" : "quiet"}>{"\u2717"} {x.failed} failed</span>
                {x.warning > 0 && <span className="warn-text">{x.warning} warning{x.warning === 1 ? "" : "s"}</span>}
                {x.skipped > 0 && <span className="quiet">{x.skipped} skipped</span>}
              </span>)}
          </div>))}
      </div>
    </div>
  );
}
