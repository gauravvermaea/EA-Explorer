// System admin > Self-test > Summary (D825; owner, 21 Nov 2026: "Please add them in one summary page for anyone to
// check"): each eax test full kept in the database, newest first, as one card a step: the dev check, the code coverage
// of our code as a ring, the self-test, the security gate, the attack test, the backup and restore test and SonarQube.
// The figures stay once the detailed files are deleted (Keep summary only, or eax test prune); the links then go.
import { useEffect, useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { fmtDateTime } from "./fmt";

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

const State = ({ ok }) => (ok == null ? <span className="pill none">not run</span>
  : ok ? <span className="pill good">passed</span> : <span className="pill bad">failed</span>);
const Rows = ({ rows }) => (
  <table className="small"><tbody>{rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v ?? "-"}</td></tr>)}</tbody></table>);

export function Cards({ s, onOpen }) {
  const steps = Object.fromEntries((s.steps || []).map((x) => [x.kind, x]));
  const run = s.selftest || {}, cov = run.coverage || {}, sec = run.security, att = run.attack;
  const unit = cov.unit ?? s.dev?.coverage?.percent;
  const goal = Number(cov.goal) || 90;
  return (
    <div className="full-cards">
      {(s.dev || steps.dev) && (
        <section className="full-card"><h3>Dev check <State ok={(steps.dev || s.dev).passed} /></h3>
          {s.dev ? <Rows rows={(s.dev.steps || []).map((x) => [x.title, `${x.passed ? "ok" : "FAILED"}${x.why ? `: ${x.why}` : ""}`])} />
            : <p className="small">{steps.dev.why}</p>}</section>)}
      <section className="full-card"><h3>Code coverage</h3>
        <div className="full-ring"><Ring percent={cov.percent} goal={goal} /></div>
        <Rows rows={[["this run alone", cov.live != null ? `${cov.live}%` : "-"], ["the unit tests alone", unit != null ? `${unit}%` : "-"],
          ["lines", cov.lines ? `${cov.run || 0} of ${cov.lines} run` : "-"], ["goal", `${goal}%`]]} />
        <p className="quiet small">Our code only: the API, the job runner and the MCP server, joined with the unit tests.</p></section>
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
    </div>
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
