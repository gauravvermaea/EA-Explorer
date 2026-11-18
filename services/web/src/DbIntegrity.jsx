// System admin › Database maintenance › Integrity (Release 6.6, R6.6.1, D750): every database's indexes, tables,
// constraints and sequences checked, and the newest records of each kind shown (to compare with a backup or the
// primary). Weekly, after every restore and when a DR site takes over, or now. Safe fixes (an index rebuilt, a
// constraint validated, a sequence moved on) happen by themselves after a backup; orphan rows are removed only on a
// Super Admin's yes, after a preview. The same as eax db integrity and eax db repair.
import { useState } from "react";
import { apiFetch, can } from "./auth";
import { useApi } from "./ModelViews";
import { fmtDateTime } from "./fmt";

export default function DbIntegrity() {
  const [gen, setGen] = useState(0);
  const { data, error } = useApi(`/api/v1/admin/db-integrity?g=${gen}`);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [preview, setPreview] = useState(null);
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading...</p>;
  const last = data.last;
  const wrong = (last?.findings || []).filter((f) => f.level !== "info");
  // Check now only checks; the safe fixes only when asked (Fix the safe ones) or switched on (System settings): a fix
  // takes a backup behind the maintenance page first (the owner, 18 Nov 2026, 10:18: "I didnt ask")
  const checkNow = async (fix = false) => {
    if (fix && !window.confirm("Make the safe fixes now? A backup is taken first if there is none from the last day: the maintenance page is up for a few minutes while it is.")) return;
    try { const r = await apiFetch("/api/v1/admin/db-integrity", { method: "POST", body: JSON.stringify({ fix, accept_maintenance: fix }) }); setMsg({ ok: true, text: r.message }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  };
  const safe = wrong.filter((f) => ["reindex", "validate", "sequence"].includes(f.key));
  const ask = async (f) => {
    try { setPreview({ f, ...(await apiFetch("/api/v1/admin/db-integrity/repair", { method: "POST", body: JSON.stringify({ finding: f }) })) }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  };
  const remove = async () => {
    try {
      const r = await apiFetch("/api/v1/admin/db-integrity/repair", { method: "POST", body: JSON.stringify({ confirm: preview.confirm }) });
      setMsg({ ok: true, text: `Removed ${r.removed} row(s) of ${r.table}; they are kept in the run's record.` }); setPreview(null); setGen((g) => g + 1);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  };
  return (
    <div className="db-integrity">
      <h3>Integrity</h3>
      <p className="quiet">Every database's indexes, tables, constraints and sequences, weekly (Sundays 02:20), after every restore and when a DR site
        takes over. Checking changes nothing. Safe fixes are made when you ask (Fix the safe ones), or by themselves when switched on
        (System settings › Database safe fixes by themselves); rows are removed only on a Super Admin's yes.</p>
      <div className="toolbar"><button onClick={() => checkNow(false)}>Check the integrity now</button>{" "}
        {safe.length > 0 && <button onClick={() => checkNow(true)}>Fix the safe ones</button>}
        {last && <span className="quiet small">Last: {fmtDateTime(last.at)} · {last.note}</span>}</div>
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}
      {!last ? <p className="quiet">Not checked yet.</p> : (
        <>
          {(last.actions || []).length > 0 && <p className="status ok">Fixed by itself: {(last.actions || []).map((a) => `${a.what} (${a.status})`).join("; ")}</p>}
          {wrong.length === 0 ? <p className="status ok">Every database is whole.</p> : (
            <table className="grid-table small">
              <thead><tr><th>Database</th><th>What</th><th>Detail</th><th>What happens</th><th /></tr></thead>
              <tbody>{wrong.map((f, i) => (
                <tr key={i} className={f.level === "critical" ? "bad-row" : ""}><td>{f.database}</td><td>{f.what}</td><td>{f.detail}</td><td>{f.action}</td>
                  <td>{f.key === "orphans" && can("settings.manage") && <button className="small" onClick={() => ask(f)}>Preview the repair</button>}</td></tr>))}</tbody>
            </table>)}
        </>)}
      {preview && (
        <div className="status warn">
          <p><b>{preview.count}</b> row(s) of <b>{preview.table}</b> in {preview.database} point at nothing and would be removed (kept in the run's record):</p>
          <pre className="small">{JSON.stringify(preview.sample.slice(0, 5), null, 2)}</pre>
          <button className="danger" onClick={remove}>Remove them</button> <button onClick={() => setPreview(null)}>Cancel</button>
        </div>)}
    </div>
  );
}
