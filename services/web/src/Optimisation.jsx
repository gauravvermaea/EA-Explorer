// System admin > Optimisation (R5.1, D697): the optimisation report. EA Explorer measures itself on the 1st of every
// month (and on "Measure now"); each suggestion carries its evidence, what it saves, its risk and how to undo it. Nothing
// is changed without a person's yes, and each yes is for a whole model or project: archive an unused one; a model's
// history from before its last tag condensed or removed (its Model Admin decides). The same report as Excel and as
// eax optimise. IT and Super Admins see it all; a Model Admin sees what is theirs to decide.
import { useEffect, useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { fmtDateTime } from "./fmt";

const AREAS = { server: "Server", unused: "Unused models and projects", disk: "Disk", history: "History", database: "Database" };

export default function Optimisation() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const load = () => apiFetch("/api/v1/admin/optimisation").then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (!d) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading…</p>;
  const rep = d.report;
  async function measure() {
    setBusy("measure"); setErr(""); setMsg("");
    try { const r = await apiFetch("/api/v1/admin/optimisation", { method: "POST", body: "{}" }); setMsg(`${r.suggestions.length} suggestion(s).`); load(); }
    catch (e) { setErr(e.message); }
    setBusy("");
  }
  async function apply(s, choice) {
    const what = choice ? `${choice === "condense" ? "Condense" : "Remove"} the history of ${s.params.name} from before its tag` : s.title;
    if (!window.confirm(`${what}?\n\n${s.evidence}\nRisk: ${s.risk}\nUndo: ${s.undo || "-"}`)) return;
    setBusy(s.key); setErr(""); setMsg("");
    try {
      await apiFetch(`/api/v1/admin/optimisation/${rep.id}/apply`, { method: "POST", body: JSON.stringify({ key: s.key, choice: choice || "" }) });
      setMsg(`Done: ${what}.`); load();
    } catch (e) { setErr(e.message); }
    setBusy("");
  }
  const excel = () => apiDownload(`/api/v1/admin/optimisation/${rep.id}/xlsx`, `eaexplorer-optimisation-${rep.id}.xlsx`).catch((e) => setErr(e.message));
  const applied = (rep && rep.applied) || {};
  const groups = Object.keys(AREAS).map((a) => [a, ((rep && rep.report.suggestions) || []).filter((s) => s.area === a)]).filter(([, l]) => l.length);
  return (
    <div className="optimisation">
      <p className="quiet">EA Explorer measures itself on the 1st of every month: the server's memory and CPU, models and projects not opened
        or changed for {d.unused_days} days (System settings), old self-test runs, Docker's build cache, history from before a model's last tag
        and the database check. Nothing is changed without a yes, and each yes is for a whole model or project. On the command line: <code>eax optimise</code>.</p>
      <div className="row-gap">
        {d.may_measure && <button onClick={measure} disabled={!!busy}>{busy === "measure" ? "Measuring…" : "Measure now"}</button>}
        {rep && <button onClick={excel}>Excel</button>}
      </div>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {!rep ? <p>No report yet.</p> : (
        <>
          <p className="small">Report {rep.id}, {fmtDateTime(rep.at)} by {rep.by_whom}
            {d.compared && ` · since the one before: ${d.compared.new} new, ${d.compared.gone} gone, ${d.compared.same} the same`}</p>
          {!groups.length && <p>Nothing to suggest{d.may_measure ? "" : " for you to decide"}.</p>}
          {groups.map(([area, list]) => (
            <div key={area}>
              <h3>{AREAS[area]}</h3>
              <table className="grid-table small">
                <thead><tr><th>Suggestion</th><th>Evidence</th><th>Created by and admins</th><th>Saves</th><th>Risk</th><th>How to undo</th><th /></tr></thead>
                <tbody>{list.map((s) => (
                  <tr key={s.key}>
                    <td>{s.title}</td><td>{s.evidence}</td>
                    <td className="small">{Object.entries(s.people || {}).filter(([, v]) => v && v.length).map(([k, v]) => (
                      <div key={k}>{k}: {Array.isArray(v) ? v.join(", ") : v}</div>))}</td><td>{s.saves}</td><td>{s.risk}</td><td>{s.undo}</td>
                    <td>{applied[s.key] ? <span className="quiet">Applied by {applied[s.key].by}{applied[s.key].choice ? ` (${applied[s.key].choice})` : ""}</span>
                      : !s.apply ? <span className="quiet">{s.who === "it-admin" ? "For IT to act on" : ""}</span>
                        : s.choices.length ? s.choices.map((c) => (
                          <button key={c} className="small" disabled={!!busy} onClick={() => apply(s, c)}>{c === "condense" ? "Condense…" : "Remove…"}</button>))
                          : <button className="small" disabled={!!busy} onClick={() => apply(s)}>Apply…</button>}</td>
                  </tr>))}</tbody>
              </table>
            </div>))}
        </>)}
    </div>
  );
}
