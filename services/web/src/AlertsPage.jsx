// System admin > Alerts (R5.9, D689): every check with its state, the open alerts first; acknowledge, silence and plan a
// downtime; each check's levels; checks of your own; who gets the email; the history. Checked every minute.
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";
import { fmtDateTime } from "./fmt";

const MARK = { OK: "✓", WARNING: "⚠", CRITICAL: "⛔", UNKNOWN: "?" };

export function AlertSummary() {
  const [s, setS] = useState(null);
  useEffect(() => { if (can("system.operate")) apiFetch("/api/v1/admin/alerting/summary").then(setS).catch(() => {}); }, []);
  if (!s || !s.open) return null;
  return <p className={`status ${s.critical ? "bad" : "warn"}`}><a href="#/admin/alerts">{s.open} open alert(s)</a>
    {s.critical ? `, ${s.critical} critical` : ""}{s.unacknowledged ? `, ${s.unacknowledged} not acknowledged` : ""}.</p>;
}

export default function AlertsPage() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [custom, setCustom] = useState({ key: "", name: "", kind: "url", target: "", warning: "1000", critical: "5000" });
  const load = () => apiFetch("/api/v1/admin/alerting").then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, []);
  if (!can("system.operate")) return <p className="quiet">Alerts are seen by IT Admins, Auditors and Super Admins.</p>;
  if (!d) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading the alerts…</p>;
  const sup = can("settings.manage");
  async function call(path, body, done) {
    setErr(""); setMsg("");
    try { const r = await apiFetch(path, { method: "POST", body: JSON.stringify(body || {}) }); setMsg(done(r)); load(); }
    catch (e) { setErr(e.message); }
  }
  const ack = (k) => { const note = window.prompt("Acknowledge: a note (what is being done)?", ""); if (note !== null) call(`/api/v1/admin/alerting/${encodeURIComponent(k)}/ack`, { note }, () => "Acknowledged: it stops repeating."); };
  const silence = (k) => {
    const m = window.prompt(k ? `Silence ${k} for how many minutes?` : "A planned downtime: silence every check for how many minutes?", "60");
    if (!m) return;
    const reason = window.prompt("Why?", k ? "" : "planned downtime") || "";
    call("/api/v1/admin/alerting/silence", { key: k || "*", minutes: Number(m), reason }, (r) => `Silenced until ${fmtDateTime(r.until)}.`);
  };
  const levels = (c) => {
    const w = window.prompt(`${c.what}: warning at (${c.unit})?`, String(c.warning)); if (w === null) return;
    const x = window.prompt(`${c.what}: critical at (${c.unit})?`, String(c.critical)); if (x === null) return;
    call(`/api/v1/admin/alerting/${encodeURIComponent(c.key)}/config`, { warning: Number(w), critical: Number(x) }, () => "Saved.");
  };
  async function history() {
    try {
      const r = await apiFetch("/api/v1/admin/alerting/history");
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([r.csv], { type: "text/csv" })); a.download = r.name; a.click();
    } catch (e) { setErr(e.message); }
  }
  return (
    <div className="alerts-admin">
      <p className="quiet">Checked every minute. A state counts once it holds for two checks; an alert goes to the IT Admins and Super Admins,
        the webhooks{d.email.host ? " and by email" : ""}, again every hour until acknowledged, and to the Super Admins when not acknowledged
        within 30 minutes. Maintenance and a self-test running are downtimes by themselves.</p>
      <p><strong>{d.open}</strong> open ({d.critical} critical, {d.unacknowledged} not acknowledged).{" "}
        <button onClick={() => silence("")}>Plan a downtime…</button>{" "}<button onClick={history}>Download the history (CSV)</button></p>
      {d.silences.length > 0 && <p className="status warn">Silenced: {d.silences.map((s) => `${s.check_key === "*" ? "everything" : s.check_key} until ${fmtDateTime(s.until)}`).join("; ")}.</p>}
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      <table className="grid-table">
        <thead><tr><th>State</th><th>Check</th><th>Now</th><th>Since</th><th>Acknowledged</th><th /></tr></thead>
        <tbody>{d.checks.map((c) => (
          <tr key={c.check_key} className={c.state === "CRITICAL" ? "bad" : c.state === "WARNING" ? "warn" : ""}>
            <td><span aria-hidden="true">{MARK[c.state]}</span> {c.state}{c.flapping ? " (flapping)" : ""}</td>
            <td>{c.what}<div className="small quiet">{c.check_key}</div></td>
            <td>{c.message}</td><td>{fmtDateTime(c.since)}</td>
            <td>{c.acked_by ? `${c.acked_by}${c.ack_note ? `: ${c.ack_note}` : ""}` : ""}</td>
            <td>{["WARNING", "CRITICAL"].includes(c.state) && !c.acked_by && <button className="small" onClick={() => ack(c.check_key)}>Acknowledge</button>}
              {" "}<button className="small" onClick={() => silence(c.check_key)}>Silence</button></td>
          </tr>))}</tbody>
      </table>
      <h3>Levels</h3>
      <table className="grid-table small">
        <thead><tr><th>Check</th><th>Warning</th><th>Critical</th><th>Unit</th><th /></tr></thead>
        <tbody>{d.config.map((c) => (
          <tr key={c.key}><td>{c.what}</td><td>{c.warning}</td><td>{c.critical}</td><td>{c.unit}</td>
            <td>{sup && <button className="small" onClick={() => levels(c)}>Change</button>}
              {sup && c.custom && <> <button className="small" onClick={() => call(`/api/v1/admin/alerting/${encodeURIComponent(c.key)}/delete`, {}, () => "Removed.")}>Remove</button></>}</td></tr>))}</tbody>
      </table>
      {sup && (
        <fieldset>
          <legend>A check of your own</legend>
          <label>Key <input value={custom.key} onChange={(e) => setCustom({ ...custom, key: e.target.value })} /></label>{" "}
          <label>Name <input value={custom.name} onChange={(e) => setCustom({ ...custom, name: e.target.value })} /></label>{" "}
          <label>Kind <select value={custom.kind} onChange={(e) => setCustom({ ...custom, kind: e.target.value })}>
            <option value="url">An address answers (ms)</option><option value="sql">A read-only query returns a number</option></select></label>
          <div><label>Address or query <input className="wide" value={custom.target} onChange={(e) => setCustom({ ...custom, target: e.target.value })} /></label></div>
          <label>Warning at <input type="number" value={custom.warning} onChange={(e) => setCustom({ ...custom, warning: e.target.value })} /></label>{" "}
          <label>Critical at <input type="number" value={custom.critical} onChange={(e) => setCustom({ ...custom, critical: e.target.value })} /></label>{" "}
          <button onClick={() => call("/api/v1/admin/alerting/custom", { ...custom, warning: Number(custom.warning), critical: Number(custom.critical) }, () => "Added: checked from the next minute.")}>Add the check</button>
        </fieldset>)}
      <h3>Email</h3>
      <p className="small">{d.email.host ? `Through ${d.email.host}:${d.email.port} (${d.email.security}) from ${d.email.sender}` : "No mail server set (EAX_SMTP_HOST in the config file): no email is sent."}
        {" "}To: {d.email.to.length ? d.email.to.join(", ") : "nobody yet (System admin › System settings, Alerts: email to)"}.</p>
      {sup && d.email.host && <button onClick={() => call("/api/v1/admin/alerting/test-email", {}, (r) => `A test email went to ${r.sent_to.join(", ")}.`)}>Send a test email</button>}
    </div>
  );
}
