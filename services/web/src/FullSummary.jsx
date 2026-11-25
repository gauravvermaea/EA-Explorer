// System admin > Self-test > Summary (D825; owner, 21 Nov 2026: "Please add them in one summary page for anyone to
// check"): each eax test full kept in the database, newest first, as one card a step: the dev check, the code coverage
// of our code as a ring, the self-test, the security gate, the attack test, the backup and restore test and SonarQube.
// The figures stay once the detailed files are deleted (Keep summary only, or eax test prune); the links then go.
import { useEffect, useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { fmtDateTime, fmtNumber } from "./fmt";

const GOOD = "#1a7f37", NEAR = "#b7791f", LOW = "#c62828", GREY = "#8a8f98";

export function Ring({ percent, goal = 90, size = 140, label = "our code" }) {
  const r = size / 2 - 12, w = 16, c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(100, Number(percent) || 0));
  const colour = percent == null ? GREY : p >= goal ? GOOD : p >= goal - 15 ? NEAR : LOW;
  const a = (goal / 100) * 2 * Math.PI - Math.PI / 2;
  const text = percent == null ? "no figure" : `${p.toFixed(1)}%`;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={`${label}: ${text} of the lines run, goal ${goal}%`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e3e6ea" strokeWidth={w} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={colour} strokeWidth={w}
        strokeDasharray={`${(c * p) / 100} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <line x1={size / 2 + r * Math.cos(a)} y1={size / 2 + r * Math.sin(a)} x2={size / 2 + (r - w) * Math.cos(a)}
        y2={size / 2 + (r - w) * Math.sin(a)} stroke="#222" strokeWidth="2" />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" fontSize="20" fontWeight="600">{text}</text>
      <text x="50%" y="66%" textAnchor="middle" fontSize="11" fill="#555">{label}</text>
    </svg>
  );
}

// How far a figure is from its bar, as the owner reads it (25 Nov 2026, 16:24: "show the actual measure that you say
// here"): "short by 6.7 points: about 783 more lines to run", or "at or over the bar".
export function toReach(percent, bar, total, done, what) {
  if (percent == null || !total) return "-";
  const p = Number(percent), b = Number(bar) || 90;
  if (p >= b) return `at or over the ${what === "screens" ? "bar" : "goal"} of ${b}%`;
  const more = Math.max(0, Math.ceil((b * Number(total)) / 100 - Number(done || 0)));
  return `short by ${(b - p).toFixed(1)} points: about ${fmtNumber(more, 0)} more ${what === "screens" ? "screens covered" : "lines to run"}`;
}

// The overall coverage (owner, 25 Nov 2026, 16:34: "can there a an overall coverage ring too, these two can be under it"):
// the API's and the screens' figures counted equally, to one decimal; one alone when only it was measured. Bar 90%. As
// eaxcli/fullreport.overall and coverage_view.overall.
export function overall(api, screens) {
  const got = [api, screens].filter((x) => x != null).map(Number);
  return got.length ? Math.round((got.reduce((a, b) => a + b, 0) / got.length) * 10) / 10 : null;
}

const State = ({ ok }) => (ok == null ? <span className="pill none">not run</span>
  : ok ? <span className="pill good">passed</span> : <span className="pill bad">failed</span>);
const Rows = ({ rows }) => (
  <table className="small"><tbody>{rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v ?? "-"}</td></tr>)}</tbody></table>);

export function Cards({ s, onOpen }) {
  const steps = Object.fromEntries((s.steps || []).map((x) => [x.kind, x]));
  const run = s.selftest || {}, cov = run.coverage || {}, sec = run.security, att = run.attack;
  const unit = cov.unit ?? s.dev?.coverage?.percent;
  const goal = Number(cov.goal) || 90;
  const api = cov.api ?? null, scr = run.screens;     // the goal's measure (eax/api) and the screens (D926)
  const whole = api != null && scr ? overall(api, scr.percent) : null;
  const where = [whole != null && `Overall ${whole}% (the API and the screens counted equally), bar 90%: ${whole >= 90 ? "at or over the bar" : `short by ${(90 - whole).toFixed(1)} points`}`,
    api != null && `The API ${api}% of ${cov.api_lines} lines, goal ${goal}%: ${toReach(api, goal, cov.api_lines, cov.api_run, "lines")}`,
    cov.jobs != null && `background jobs ${cov.jobs}% (shown, not judged)`,
    scr && `the screens ${scr.percent}% (${scr.covered} of ${scr.screens}), bar ${Number(scr.bar) || 90}%: ${toReach(scr.percent, scr.bar, scr.screens, scr.covered, "screens")}`]
    .filter(Boolean);
  return (<>
    {where.length > 0 && <p className="full-where"><b>Where it stands:</b> {where.join("; ")}.</p>}
    <div className="full-cards">
      {(s.dev || steps.dev) && (
        <section className="full-card"><h3>Dev check <State ok={(steps.dev || s.dev).passed} /></h3>
          {s.dev ? <Rows rows={(s.dev.steps || []).map((x) => [x.title, `${x.passed ? "ok" : "FAILED"}${x.why ? `: ${x.why}` : ""}`])} />
            : <p className="small">{steps.dev.why}</p>}</section>)}
      {whole != null && (
        <section className="full-card full-overall"><h3>Overall coverage</h3>
          <div className="full-ring"><Ring percent={whole} goal={90} size={190} label="overall" /></div>
          <div className="full-pair">
            <Ring percent={api} goal={goal} size={120} label="the API" />
            <Ring percent={scr.percent} goal={Number(scr.bar) || 90} size={120} label="the screens" />
          </div>
          <p className="quiet small">Overall: the API ({api}%) and the screens ({scr.percent}%) counted equally. Bar 90%:{" "}
            {whole >= 90 ? "at or over it" : `short by ${(90 - whole).toFixed(1)} points`}. Each is in full in its own card below.</p>
        </section>)}
      <section className="full-card"><h3>Code coverage</h3>
        <div className="full-ring"><Ring percent={api ?? cov.percent} goal={goal} label={api != null ? "the API" : "our code"} /></div>
        <Rows rows={[
          ...(api != null ? [["the API (eax/api), the goal's measure", `${api}% (${cov.api_run || 0} of ${cov.api_lines || 0} lines)`],
            ["to reach the goal", toReach(api, goal, cov.api_lines, cov.api_run, "lines")],
            ...(cov.api_left_out ? [["left out of the goal", `${cov.api_left_out} lines: pairing, the routes that stop, restart, restore or wipe the installation, the self-test's own controls`]] : []),
            ...(cov.jobs != null ? [["the background jobs", `${cov.jobs}% (${cov.jobs_run || 0} of ${cov.jobs_lines || 0} lines)`]] : []),
            ["the risky suite (--risky)", cov.risky ? "on: the routes it runs count" : "off: its routes left out"],
            ["all the server's code", `${cov.percent}%`]] : []),
          ["this run alone", cov.live != null ? `${cov.live}%` : "-"], ["the unit tests alone", unit != null ? `${unit}%` : "-"],
          ["lines", cov.lines ? `${cov.run || 0} of ${cov.lines} run` : "-"], ["goal", `${goal}%`]]} />
        <p className="quiet small">{api != null ? "The goal is measured on the API (eax/api); the rest of our code is shown, not judged."
          : "Our code only: the API, the job runner and the MCP server, joined with the unit tests."}</p></section>
      {scr && (
        <section className="full-card"><h3>Screens covered by journeys</h3>
          <div className="full-ring"><Ring percent={scr.percent} goal={Number(scr.bar) || 90} label="the screens" /></div>
          <Rows rows={[["screens covered", `${scr.covered} of ${scr.screens}`],
            ["to reach the bar", toReach(scr.percent, scr.bar, scr.screens, scr.covered, "screens")], ["acted on by a journey", scr.acted_on],
            ["read only and opened", scr.read_only], ["controls used", `${scr.controls_used} of ${scr.controls} (${scr.controls_percent}%)`],
            ["risky controls left out", scr.left_out], ["screens left out", scr.screens_left_out], ["bar", `${Number(scr.bar) || 90}%`]]} />
          <p className="quiet small">A screen is covered when a journey acts on it, or it only shows and opens. The bar: 90% of the screens counted.</p>
        </section>)}
      {(s.selftest || steps.selftest) && (
        <section className="full-card"><h3>Self-test <State ok={steps.selftest ? steps.selftest.passed : run.state === "passed"} /></h3>
          <p><b>{run.tally?.passed || 0}</b> passed · <b>{run.tally?.failed || 0}</b> failed · {run.tally?.warning || 0} warnings · {run.tally?.skipped || 0} skipped</p>
          {run.health && <p className="small">Functional health: <b>{run.health}</b> {run.reason}</p>}
          <Rows rows={Object.entries(run.by_suite || {}).map(([k, v]) => [k, `${v.passed} passed, ${v.failed} failed, ${v.warning} warnings`])} />
          {run.run && <button className="linkish" onClick={() => onOpen(run.run)}>Self-test {run.run}: its results</button>}</section>)}
      {sec && (
        <section className="full-card"><h3>Security gate <State ok={!sec.failing} /></h3>
          <Rows rows={[["findings", sec.findings], ["high or critical, not accepted", sec.failing], ["accepted in writing", sec.accepted],
            ["accepted until a date now past", sec.expired], ["no fix released yet", sec.no_fix], ["new since the run before", sec.new]]} /></section>)}
      {att && (
        <section className="full-card"><h3>Attack test</h3>
          <Rows rows={Object.entries(att.tools || {}).map(([n, t]) => [n, t.pulled ? "the newest" : t.present ? "the last pulled" : "not there: left out"])} />
          <h4>Findings</h4>
          <Rows rows={Object.entries(att.findings || {}).map(([src, by]) => [src, Object.entries(by).map(([k, v]) => `${v} ${k}`).join(", ")])} />
        </section>)}
      {(s.backup || steps.backup) && (
        <section className="full-card"><h3>Backup and restore <State ok={(steps.backup || s.backup).passed} /></h3>
          {s.backup ? <><p><b>{s.backup.checks - s.backup.failed}</b> of {s.backup.checks} checks passed</p>
            {(s.backup.failures || []).length > 0 && <ul className="small">{s.backup.failures.map((f) => <li key={f}>{f}</li>)}</ul>}</>
            : <p className="small">{steps.backup.why}</p>}</section>)}
      {(s.sonar || steps.sonar) && (
        <section className="full-card"><h3>SonarQube <State ok={(steps.sonar || s.sonar).passed} /></h3>
          {s.sonar ? <Rows rows={[["to fix", s.sonar.to_fix], ["issues", s.sonar.issues], ["security hotspots", s.sonar.hotspots],
            ["accepted in writing", s.sonar.accepted], ...Object.entries(s.sonar.by_severity || {}).map(([k, v]) => [`severity ${k.toLowerCase()}`, v])]} />
            : <p className="small">{steps.sonar.why}</p>}</section>)}
      {steps.containers && (
        <section className="full-card"><h3>Test containers <State ok={steps.containers.passed} /></h3>
          <p className="small">{steps.containers.passed ? "None left running: every scanner, k6 and the test runner removed when done."
            : steps.containers.why}</p></section>)}
    </div>
    <Gaps g={s.gaps} />
  </>);
}

// What is not covered, a table a kind (owner, 25 Nov 2026, 12:19: "In the coverage clearly call out areas not being covered
// in a table"): the same tables as the summary page (eaxcli/fullreport.gaps_card), from the full test's summary.
const Table = ({ head, rows }) => (!rows.length ? <p className="quiet small">None.</p>
  : <table className="small"><thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table>);

export function Gaps({ g }) {
  if (!g) return null;
  const missed = (f) => (Number(f.lines) || 0) - (Number(f.run) || 0);
  const api = g.api_files || [], out = g.api_left_out || [], jobs = g.jobs_files || [];
  const nc = g.screens_not_covered || [], sl = g.screens_left_out || [];
  return (
    <section className="full-card full-wide"><h3>Not covered yet</h3>
      <h4>The API: files under the goal of {Number(g.api_goal) || 90}% ({api.length})</h4>
      <Table head={["file", "covered", "lines not run"]} rows={api.map((f) => [f.file, `${f.percent}%`, missed(f)])} />
      <h4>The API: left out of the goal ({out.length})</h4>
      <Table head={["file", "route", "methods", "why"]}
        rows={out.map((x) => [x.file, x.route, Array.isArray(x.methods) ? x.methods.join(", ") : (x.methods || "all"), x.why])} />
      <h4>Background jobs (shown, not judged)</h4>
      <Table head={["file", "covered", "lines not run"]} rows={jobs.map((f) => [f.file, `${f.percent}%`, missed(f)])} />
      <h4>Screens not covered yet, by area ({nc.reduce((n, x) => n + x.screens.length, 0)})</h4>
      <Table head={["area", "screens", "which"]} rows={nc.map((x) => [x.area, x.screens.length, x.screens.join(", ")])} />
      <h4>Screens left out of the bar ({sl.length})</h4>
      <Table head={["screen", "why"]} rows={sl.map((x) => [x.screen, x.why])} />
      <p className="quiet small">{Number(g.controls_left_out) || 0} risky controls (stop, restart, restore, delete, ...) are not pressed and not
        counted; they are listed in screens-coverage.json.</p>
    </section>
  );
}

export default function FullSummary({ onOpen }) {
  const [list, setList] = useState(null);
  const [pick, setPick] = useState(null);
  const [one, setOne] = useState(null);
  const [msg, setMsg] = useState("");
  const load = () => apiFetch("/api/v1/admin/tests/full").then((r) => {
    setList(r.full_tests || []);
    setPick((p) => p ?? (r.full_tests || [])[0]?.id ?? null);
  }).catch((e) => setMsg(e.message));
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (pick == null) return;
    setOne(null);
    apiFetch(`/api/v1/admin/tests/full/${pick}`).then(setOne).catch((e) => setMsg(e.message));
  }, [pick]);
  const prune = async () => {
    // eslint-disable-next-line no-alert
    if (!window.confirm("Delete this full test's detailed files (its steps' reports, logs, videos, scanners' reports and screenshots)? Its summary stays.")) return;
    try {
      const r = await apiFetch("/api/v1/admin/tests/prune", { method: "POST", body: JSON.stringify({ fulls: [one.id] }) });
      setMsg(r.message); void load();
      setOne(await apiFetch(`/api/v1/admin/tests/full/${one.id}`));
    } catch (e) { setMsg(e.message); }
  };
  if (!list) return <p className="quiet"><span className="spinner" aria-hidden="true" /> Reading the full tests...</p>;
  if (!list.length) return <p className="quiet">No full test yet. <code>eax test full</code> runs everything but the benchmark and
    ends with one summary page; it shows here.</p>;
  const s = one?.summary || {};
  return (
    <div className="full-summary">
      <div className="row-gap filters">
        <label className="small">Full test <select value={pick ?? ""} onChange={(e) => setPick(Number(e.target.value))}>
          {list.map((f) => <option key={f.id} value={f.id}>{f.id}: {fmtDateTime(f.finished_at)} · {f.passed ? "passed" : "failed"}
            {f.files_deleted_at ? " · summary only" : ""}</option>)}</select></label>
        {one?.page && <button className="linkish" onClick={() => apiDownload(`/api/v1/admin/tests/full/${one.id}/page`, `full-test-${one.id}.html`)
          .catch((e) => setMsg(e.message))}>Download the summary page</button>}
        {one && !one.files_deleted_at && <button onClick={prune}>Keep the summary only...</button>}
        {msg && <span className="small">{msg}</span>}
      </div>
      {!one ? <p className="quiet"><span className="spinner" aria-hidden="true" /> Reading...</p> : <>
        <h3>Full test {one.id} <State ok={one.passed} /></h3>
        <p className="quiet small">Version {one.version || "?"} · began {fmtDateTime(one.started_at)} · ended {fmtDateTime(one.finished_at)}
          {one.started_by ? ` · by ${one.started_by}` : ""} · <code>work/tests/{one.folder}/index.html</code>
          {one.files_deleted_at ? ` · detailed files deleted ${fmtDateTime(one.files_deleted_at)} by ${one.files_deleted_by}` : ""}</p>
        <ol className="small">{(s.steps || []).map((x) => <li key={x.title}>{x.passed ? "ok" : <b>FAILED</b>} {x.title}{x.why ? `: ${x.why}` : ""}</li>)}</ol>
        <Cards s={s} onOpen={onOpen} />
      </>}
    </div>
  );
}
