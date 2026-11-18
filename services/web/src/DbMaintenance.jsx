// System admin > Database maintenance (R5.12, D691): every database checked, in plain words; the nightly tidy and a
// tidy now; compacting one table (it locks it: Super Admin, asked first); the keep-for rules now; who blocks whom, with
// cancel and end after a preview; the history of every run. The same as eax db on the command line.
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";
import { fmtDateTime, fmtNumber } from "./fmt";
import DbIntegrity from "./DbIntegrity";

const MB = (b) => `${fmtNumber(Math.round((b || 0) / 1048576))} MB`;

export default function DbMaintenance() {
  const [d, setD] = useState(null);
  const [found, setFound] = useState(null);
  const [plan, setPlan] = useState(null);
  const [sessions, setSessions] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const load = () => apiFetch("/api/v1/admin/db-maintenance").then((x) => { setD(x); if (!found && x.last_check) setFound(x.last_check); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!can("system.operate")) return <p className="quiet">Database maintenance is for IT Admins and Super Admins (Auditors see it).</p>;
  if (!d) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading…</p>;
  const sup = can("settings.manage");
  async function post(what, body, done) {
    setBusy(what); setErr(""); setMsg("");
    try { const r = await apiFetch(`/api/v1/admin/db-maintenance/${what}`, { method: "POST", body: JSON.stringify(body || {}) }); done(r); load(); }
    catch (e) { setErr(e.message); }
    setBusy("");
  }
  const check = () => post("check", {}, (r) => { setFound(r); setMsg(`${r.findings.length} finding(s).`); });
  const tidyPlan = () => post("tidy", { dry_run: true }, (r) => setPlan(r.actions));
  const tidy = () => post("tidy", {}, (r) => { setPlan(null); setMsg(`Tidied: ${r.actions.filter((a) => a.status === "done").length} step(s) done.`); });
  const clear = () => window.confirm("Apply the keep-for rules now (housekeeping, old alert history)?") && post("clear", {}, () => setMsg("The keep-for rules were applied."));
  async function compact(f) {
    setErr("");
    try {
      const p = await apiFetch("/api/v1/admin/db-maintenance/compact-preview", { method: "POST", body: JSON.stringify({ database: f.database, table: f.target }) });
      if (!window.confirm(`${p.table} (${MB(p.bytes)}): about ${MB(p.about_to_win)} to win. ${p.warning} Compact it now?`)) return;
      post("compact", { confirm: p.confirm }, (r) => setMsg(`Compacted ${r.table}: ${MB(r.won)} won.`));
    } catch (e) { setErr(e.message); }
  }
  const showLocks = () => apiFetch("/api/v1/admin/db-maintenance/locks").then((r) => setSessions(r.sessions)).catch((e) => setErr(e.message));
  async function stop(s, end) {
    try {
      const p = await apiFetch("/api/v1/admin/db-maintenance/stop-preview", { method: "POST", body: JSON.stringify({ pid: s.pid, end }) });
      if (!window.confirm(`${p.action}: session ${p.pid} (${p.login}, ${p.state}) running ${p.query}?`)) return;
      post("stop", { confirm: p.confirm }, (r) => { setMsg(r.done ? "Done." : "It had already ended."); showLocks(); });
    } catch (e) { setErr(e.message); }
  }
  return (
    <div className="db-maintenance">
      <p className="quiet">Every database on the server is checked every day at 00:50 and tidied every night between {d.settings.window_start} and
        {" "}{d.settings.window_end} (nothing is locked). Sessions idle in a transaction are ended after {d.settings.idle_tx_minutes} minutes.
        Nothing runs during a backup, a restore or a self-test. On the command line: <code>eax db</code>.</p>
      {d.busy && <p className="status warn">Waiting: {d.busy}.</p>}
      <div className="row-gap">
        <button onClick={check} disabled={!!busy}>{busy === "check" ? "Checking…" : "Check now"}</button>
        <button onClick={tidyPlan} disabled={!!busy}>What a tidy would do</button>
        {sup && <button onClick={clear} disabled={!!busy}>Apply the keep-for rules now</button>}
        <button onClick={showLocks}>Who blocks whom</button>
      </div>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {plan && (
        <div>
          <h3>A tidy would run</h3>
          {plan.length ? <ul>{plan.map((a, i) => <li key={i}><code>{a.sql}</code> in {a.database}</li>)}</ul> : <p>Nothing: every database is tidy.</p>}
          {plan.length > 0 && <button className="primary" onClick={tidy} disabled={!!busy}>Tidy now</button>}
        </div>)}
      {found && (
        <div>
          <h3>Findings {found.at && <span className="small quiet">({fmtDateTime(found.at)})</span>}</h3>
          {(found.databases || []).length > 0 && <p className="small">{found.databases.map((x) => `${x.database}: ${MB(x.bytes)}, cache ${x.cache_hit}%`).join(" · ")}</p>}
          {!found.findings.length ? <p>Nothing needs doing.</p> : (
            <table className="grid-table small">
              <thead><tr><th>Level</th><th>Database</th><th>What</th><th>Detail</th><th>What to do</th><th /></tr></thead>
              <tbody>{found.findings.map((f, i) => (
                <tr key={i} className={f.level === "critical" ? "bad" : f.level === "warning" ? "warn" : ""}>
                  <td>{f.level}</td><td>{f.database}</td><td>{f.what}</td><td>{f.detail}</td><td>{f.action}</td>
                  <td>{sup && f.key === "bloat" && <button className="small" onClick={() => compact(f)}>Compact…</button>}</td>
                </tr>))}</tbody>
            </table>)}
        </div>)}
      {sessions && (
        <div>
          <h3>Sessions holding or waiting for locks</h3>
          {!sessions.length ? <p>None.</p> : (
            <table className="grid-table small">
              <thead><tr><th>Session</th><th>Database</th><th>Login</th><th>State</th><th>Seconds</th><th>Blocked by</th><th>Query</th><th /></tr></thead>
              <tbody>{sessions.map((s) => (
                <tr key={s.pid}><td>{s.pid}</td><td>{s.database}</td><td>{s.login}</td><td>{s.state}</td><td>{s.seconds}</td>
                  <td>{(s.blocked_by || []).join(", ")}</td><td className="small">{s.query}</td>
                  <td><button className="small" onClick={() => stop(s, false)}>Cancel query</button>{" "}
                    <button className="small" onClick={() => stop(s, true)}>End session</button></td></tr>))}</tbody>
            </table>)}
        </div>)}
      <DbIntegrity />
      <h3>History</h3>
      <table className="grid-table small">
        <thead><tr><th>When</th><th>What</th><th>By</th><th>Found</th><th>Done</th><th>Status</th></tr></thead>
        <tbody>{d.history.map((h) => <tr key={h.id}><td>{fmtDateTime(h.at)}</td><td>{h.kind}</td><td>{h.by_whom}</td><td>{h.found}</td><td>{h.done}</td><td>{h.status}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
