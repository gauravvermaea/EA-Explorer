// Architecture in sprints, for a project of the Agile type (Release 12, R12.2; D858, D879; TOGAF Series Guide: Applying
// the TOGAF ADM using Agile Sprints). The project's Sprints tab: the backlog (offered from the requirements, epics and
// features in its models, D880: nothing taken in by itself; deliverables and items added by hand), the open sprint with
// its goal, dates, phases, steps and who accepts it, its review (each item accepted or back to the backlog), the
// sprints before it, and the usual sprint length. Only an Agile project has this tab.
import { useState } from "react";
import { apiFetch } from "./auth";
import { fmtDate } from "./fmt";
import { refreshAll, useApi } from "./ModelViews";

const STATUS = { planned: "planned", open: "open", reviewed: "reviewed" };

function Offered({ p, onDone, onError }) {
  const { data } = useApi(`/api/v1/projects/${p.id}/agile/offered`);
  const [pick, setPick] = useState({});
  const list = data?.offered || [];
  if (!data) return <p className="quiet small">Looking in the project's models...</p>;
  if (!list.length) return <p className="quiet small">Nothing to offer: every requirement, epic and feature in the project's models is in the backlog.</p>;
  const take = async () => {
    try {
      await apiFetch(`/api/v1/projects/${p.id}/agile/backlog`, { method: "POST", body: JSON.stringify({ entities: Object.keys(pick).filter((k) => pick[k]) }) });
      setPick({}); onDone();
    } catch (e) { onError(e.message); }
  };
  return (
    <details>
      <summary>Offered from the project's models ({list.length})</summary>
      <p className="quiet small">Requirements, security requirements, epics and features not in the backlog yet. Tick those to take in.</p>
      <ul className="plain">{list.map((o) => (
        <li key={o.entity}><label><input type="checkbox" checked={!!pick[o.entity]} onChange={(e) => setPick({ ...pick, [o.entity]: e.target.checked })} />{" "}
          {o.name} <span className="quiet small">{o.type} · {o.model_name}</span></label></li>))}</ul>
      <button disabled={!Object.values(pick).some(Boolean)} onClick={take}>Take into the backlog</button>
    </details>
  );
}

function PlanSprint({ p, d, onDone, onError }) {
  const first = d.sprints.length === 0;
  const [f, setF] = useState({ goal: "", starts_on: "", ends_on: "", phases: [], accepter: "", items: [], zero: false });
  const set = (k, v) => setF({ ...f, [k]: v });
  const toggle = (k, v) => set(k, f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v]);
  const go = async () => {
    try {
      await apiFetch(`/api/v1/projects/${p.id}/agile/sprints`, { method: "POST", body: JSON.stringify(f) });
      onDone();
    } catch (e) { onError(e.message); }
  };
  return (
    <section className="card">
      <h3>Plan the next sprint</h3>
      {first && <label className="small"><input type="checkbox" checked={f.zero} onChange={(e) => set("zero", e.target.checked)} /> Make it Sprint zero, the
        strategic sprint: the foundation (business needs, capabilities, value streams, a high-level roadmap) that fills the backlog for the sprints after it</label>}
      <p className="quiet small">Usually {d.sprint_days} days: leave the end empty to use it, or give the sprint its own dates.</p>
      <label>Goal (what the sprint must achieve) <input value={f.goal} required onChange={(e) => set("goal", e.target.value)} /></label>
      <label>Starts <input type="date" value={f.starts_on} onChange={(e) => set("starts_on", e.target.value)} /></label>{" "}
      <label>Ends <input type="date" value={f.ends_on} onChange={(e) => set("ends_on", e.target.value)} /></label>
      <fieldset><legend>ADM phases it runs</legend>
        {d.phases.map((ph) => <label key={ph} className="small"><input type="checkbox" checked={f.phases.includes(ph)} onChange={() => toggle("phases", ph)} /> {ph} </label>)}
      </fieldset>
      <label>Who accepts its deliverables <input value={f.accepter} placeholder="a member's username, or a name" onChange={(e) => set("accepter", e.target.value)} /></label>
      <fieldset><legend>Backlog items it takes</legend>
        {d.backlog.length ? d.backlog.map((b) => (
          <label key={b.id} className="small" style={{ display: "block" }}><input type="checkbox" checked={f.items.includes(b.id)} onChange={() => toggle("items", b.id)} />{" "}
            {b.title} <span className="quiet">{b.kind}{b.returned ? `, back ${b.returned}×` : ""}</span></label>))
          : <p className="quiet small">The backlog is empty: add to it first.</p>}
      </fieldset>
      <button className="primary" disabled={!f.goal.trim() || !f.phases.length || !f.accepter.trim() || !f.items.length} onClick={go}>Plan the sprint</button>
    </section>
  );
}

function Review({ p, s, onDone, onError }) {
  const [dec, setDec] = useState({});
  const [note, setNote] = useState("");
  const [demo, setDemo] = useState("");
  const [retro, setRetro] = useState("");
  const all = s.items.every((i) => dec[i.id] !== undefined);
  const go = async () => {
    try {
      await apiFetch(`/api/v1/projects/${p.id}/agile/sprints/${s.id}/review`, { method: "POST", body: JSON.stringify({ decisions: dec, note, demo, retrospective: retro }) });
      onDone();
    } catch (e) { onError(e.message); }
  };
  return (
    <div>
      <h4>The review <span className="quiet small">demo, outcome, retrospective, then plan the next · accepted by {s.accepter}</span></h4>
      <label>Demo: what was shown, and to whom <textarea rows="2" value={demo} onChange={(e) => setDemo(e.target.value)} /></label>
      <table className="grid-table small">
        <thead><tr><th scope="col">Item</th><th scope="col">Accepted</th><th scope="col">Not accepted (back to the backlog)</th></tr></thead>
        <tbody>{s.items.map((i) => (
          <tr key={i.id}><td>{i.title} <span className="quiet">{i.kind}</span></td>
            <td><input type="radio" name={`d-${i.id}`} aria-label={`${i.title}: accepted`} checked={dec[i.id] === true} onChange={() => setDec({ ...dec, [i.id]: true })} /></td>
            <td><input type="radio" name={`d-${i.id}`} aria-label={`${i.title}: not accepted`} checked={dec[i.id] === false} onChange={() => setDec({ ...dec, [i.id]: false })} /></td></tr>))}</tbody>
      </table>
      <label>Retrospective: how the team worked, and what changes next sprint <textarea rows="2" value={retro} onChange={(e) => setRetro(e.target.value)} /></label>
      <label>Note <input value={note} onChange={(e) => setNote(e.target.value)} /></label>{" "}
      <button className="primary" disabled={!all} onClick={go}>Record the review</button>
    </div>
  );
}

function Sprint({ p, s, onDone, onError }) {
  return (
    <section className="card">
      <h3>{s.name} <span className="chip small">{STATUS[s.status] || s.status}</span></h3>
      <p className="small">{fmtDate(s.starts_on)} to {fmtDate(s.ends_on)} · phases {s.phases.join(", ")} · accepted by {s.accepter}</p>
      {s.goal && <p>{s.goal}</p>}
      {s.steps.length > 0 && <details><summary className="small">Steps agreed ({s.steps.length})</summary><ul className="small">{s.steps.map((x) => <li key={x}>{x}</li>)}</ul></details>}
      {s.status === "reviewed" ? (
        <ul className="small">{s.items.map((i) => <li key={i.id}>{i.accepted ? "✓ accepted" : "↩ back to the backlog"}: {i.title}{i.decision_note ? ` (${i.decision_note})` : ""}</li>)}</ul>
      ) : <Review p={p} s={s} onDone={onDone} onError={onError} />}
      {s.demo_note && <p className="small"><b>Demo:</b> {s.demo_note}</p>}
      {s.retrospective && <p className="small"><b>Retrospective:</b> {s.retrospective}</p>}
      {s.review_note && <p className="quiet small">{s.review_note}</p>}
    </section>
  );
}

export default function SprintsTab({ p }) {
  const [gen, setGen] = useState(0);
  const { data: d, error } = useApi(`/api/v1/projects/${p.id}/agile?g=${gen}`);
  const [msg, setMsg] = useState("");
  const [title, setTitle] = useState("");
  const [days, setDays] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!d) return <p>Loading...</p>;
  const done = () => { setMsg(""); refreshAll(); setGen((x) => x + 1); };
  const oops = (t) => setMsg(t);
  const open = d.sprints.find((s) => s.status !== "reviewed");
  const add = async () => {
    try {
      await apiFetch(`/api/v1/projects/${p.id}/agile/backlog`, { method: "POST", body: JSON.stringify({ title }) });
      setTitle(""); done();
    } catch (e) { oops(e.message); }
  };
  const remove = async (b) => {
    try { await apiFetch(`/api/v1/projects/${p.id}/agile/backlog/${b.id}`, { method: "DELETE" }); done(); } catch (e) { oops(e.message); }
  };
  const rule = async (r) => {
    try { await apiFetch(`/api/v1/projects/${p.id}/agile/priority-rule`, { method: "PUT", body: JSON.stringify({ rule: r }) }); done(); } catch (e) { oops(e.message); }
  };
  const length = async () => {
    try { await apiFetch(`/api/v1/projects/${p.id}/agile/sprint-length`, { method: "PUT", body: JSON.stringify({ days }) }); setDays(""); done(); } catch (e) { oops(e.message); }
  };
  return (
    <div className="sprints-page">
      <p className="quiet">The architecture is built sprint by sprint: each sprint takes items from the backlog and agrees the ADM phases it
        runs, its steps and deliverables, and who accepts them. At the review each item is accepted, or goes back to the backlog.</p>
      {msg && <p className="status bad" role="status">{msg}</p>}
      <p className="small">{d.sprints.length} sprint(s) · {d.backlog.length} in the backlog · {d.accepted} accepted · sprints usually {d.sprint_days} days{" "}
        <label className="small">change to <input type="number" min="1" max="90" value={days} onChange={(e) => setDays(e.target.value)} style={{ width: "5em" }} /></label>{" "}
        <button disabled={!days} onClick={length}>Set</button></p>
      {open ? <Sprint p={p} s={open} onDone={done} onError={oops} /> : <PlanSprint p={p} d={d} onDone={done} onError={oops} />}
      <h3>Backlog</h3>
      <p className="small"><label>Prioritised by{" "}
        <select value={d.priority_rule} onChange={(e) => rule(e.target.value)}>
          {Object.entries(d.priority_rules).map(([k, v]) => <option key={k} value={k}>{v.split(":")[0]}</option>)}
        </select></label> <span className="quiet">{(d.priority_rules[d.priority_rule] || "").split(": ")[1]}</span></p>
      {d.backlog.length ? (
        <table className="grid-table small">
          <thead><tr><th scope="col">Item</th><th scope="col">Kind</th><th scope="col" className="num">Priority</th><th scope="col">Back from a sprint</th><th /></tr></thead>
          <tbody>{d.backlog.map((b) => (
            <tr key={b.id}><td>{b.title}</td><td>{b.kind}</td><td className="num">{b.priority}</td><td>{b.returned ? `${b.returned}×` : ""}</td>
              <td><button className="small" onClick={() => remove(b)}>Take out</button></td></tr>))}</tbody>
        </table>) : <p className="quiet small">Empty.</p>}
      <p><input value={title} placeholder="Add an item by its title" onChange={(e) => setTitle(e.target.value)} />{" "}
        <button disabled={!title.trim()} onClick={add}>Add</button></p>
      <Offered p={p} onDone={done} onError={oops} />
      {d.sprints.filter((s) => s.status === "reviewed").length > 0 && <h3>Sprints before</h3>}
      {d.sprints.filter((s) => s.status === "reviewed").map((s) => <Sprint key={s.id} p={p} s={s} onDone={done} onError={oops} />)}
    </div>
  );
}
