// A project's risk register (Release 12, R12.5; D879, D887; TOGAF Series Guide: Integrating Risk and Security, G152): on
// the Risks tab of the Governance log. It reads both sides: each Risk record of the log (its status, owner, review date)
// with the risk it describes in the project's models (an Assessment whose Assessment Kind is Risk: its likelihood,
// impact, residual risk and treatment, the controls that reduce it, what it bears on), and the risks in the models that
// are not in the log yet, each logged in one step. No new type and no new table for risks (D887).
import { useState } from "react";
import { apiFetch } from "./auth";
import { fmtDate } from "./fmt";
import { refreshAll, useApi } from "./ModelViews";

const LEVEL = { High: "bad", Medium: "amber", Low: "good" };

function Risk({ a }) {
  return (
    <div className="small">
      <b>{a.name}</b> <span className="quiet">({a.model_name})</span>
      {a.score != null && <span className="chip small" title={`Likelihood ${a.Likelihood} × impact ${a.Impact}`}>{a.Likelihood}×{a.Impact} = {a.score}</span>}
      {a.ResidualRisk && <span className={`rag ${LEVEL[a.ResidualRisk] || ""}`} title="Residual risk, after the controls">{a.ResidualRisk}</span>}
      {a.RiskTreatment && <span className="quiet"> · {a.RiskTreatment.toLowerCase()}</span>}
      <div className="quiet">{a.controls.length ? `Controls: ${a.controls.map((c) => c.name).join(", ")}` : <span className="rag amber">no control</span>}
        {a.bears_on.length > 0 && ` · bears on ${a.bears_on.map((x) => x.name).join(", ")}`}</div>
    </div>
  );
}

export default function RiskRegister({ p }) {
  const { data, error } = useApi(`/api/v1/projects/${p.id}/risk-register`);
  const [msg, setMsg] = useState(null);
  const [link, setLink] = useState({});
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet small">Reading the risk register...</p>;
  const call = async (url, body) => {
    try { const r = await apiFetch(url, { method: "POST", body: JSON.stringify(body) }); setMsg({ ok: true, m: r.message }); refreshAll(); }
    catch (e) { setMsg({ ok: false, m: e.message }); }
  };
  const base = `/api/v1/projects/${p.id}/risk-register`;
  return (
    <section className="ba-box">
      <h4>Risk register</h4>
      <p className="small quiet">The Risk records below with the risks they describe in the project's models (Assessments whose Assessment Kind is Risk), and the risks in the models not logged yet.
        {data.high ? <> <span className="rag bad">{data.high} high after controls</span></> : null}
        {data.no_control ? <> <span className="rag amber">{data.no_control} with no control</span></> : null}</p>
      {msg && <p className={`status ${msg.ok ? "good" : "bad"}`}>{msg.m}</p>}
      {data.entries.length > 0 && <table className="grid-table small">
        <thead><tr><th>Ref</th><th>Record</th><th>Status</th><th>Owner</th><th>Review</th><th>The risk in the architecture</th></tr></thead>
        <tbody>{data.entries.map((e) => (
          <tr key={e.record.id}>
            <td>{e.record.ref}</td><td>{e.record.title}{e.affects.length > 0 && <div className="quiet">affects {e.affects.join(", ")}</div>}</td>
            <td>{e.record.status} <span className="quiet">· {e.record.approval}</span></td><td>{e.record.owner || <span className="quiet">–</span>}</td>
            <td>{e.record.expires_on ? fmtDate(e.record.expires_on) : <span className="quiet">–</span>}</td>
            <td>{e.assessments.map((a) => <Risk key={a.id} a={a} />)}
              {e.missing.length > 0 && <div className="quiet small">no longer in the models: {e.missing.join(", ")}</div>}
              {!e.assessments.length && (data.may_log && data.not_logged.length
                ? <span className="small"><select value={link[e.record.id] || ""} onChange={(x) => setLink({ ...link, [e.record.id]: x.target.value })} aria-label={`The risk ${e.record.ref} describes`}>
                  <option value="">Describes which risk in the models?</option>
                  {data.not_logged.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.model_name})</option>)}</select>{" "}
                  <button disabled={!link[e.record.id]} onClick={() => { const a = data.not_logged.find((x) => x.id === link[e.record.id]); void call(`${base}/${e.record.id}/describes`, { model: a.model, element: a.id }); }}>Link</button></span>
                : <span className="quiet">not linked to a risk in the models</span>)}</td>
          </tr>))}</tbody></table>}
      {data.not_logged.length > 0 && <>
        <h5>In the models, not in the log yet</h5>
        <table className="grid-table small"><tbody>{data.not_logged.map((a) => (
          <tr key={a.id}><td><Risk a={a} /></td><td>{a.Owner || <span className="quiet">no owner</span>}</td>
            <td>{data.may_log && <button onClick={() => call(base, { model: a.model, element: a.id })}>Log it</button>}</td></tr>))}</tbody></table></>}
      {!data.entries.length && !data.not_logged.length && <p className="quiet small">{data.models ? "No risks yet: an Assessment whose Assessment Kind is Risk in one of the project's models, or a Risk record here." : "The project has no model yet."}</p>}
    </section>
  );
}
