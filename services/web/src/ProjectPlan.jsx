// A project's plan (Release 12, R12.4; D879, D884, D889; TOGAF Series Guide: Project Management and the ADM, G188): the
// Project plan tab. The settings chosen at setup (how RACI is recorded: not at all, per phase, per deliverable or per
// step; the approval gates, phases that are only complete once their deliverables are approved; the roadmap's period),
// the plan of the phases, the milestones, the RACI, the status reports, and the roadmap of the primary working model for
// the period chosen. Every project has this tab; a project that chooses no RACI and no gates works as before.
import { useState } from "react";
import { apiFetch } from "./auth";
import { fmtDate, fmtDateTime } from "./fmt";
import { Roadmap } from "./Maps";
import { refreshAll, useApi } from "./ModelViews";

const RAG_CLASS = { green: "good", amber: "amber", red: "bad" };

function Settings({ p, plan, onSaved, onError }) {
  const s = plan.settings;
  const [d, setD] = useState({ raci: s.raci, gates: s.gates, roadmap_from: s.roadmap_from || "", roadmap_to: s.roadmap_to || "", roadmap_marks: s.roadmap_marks });
  const toggle = (code) => setD({ ...d, gates: d.gates.includes(code) ? d.gates.filter((g) => g !== code) : [...d.gates, code] });
  const save = async () => {
    try {
      const r = await apiFetch(`/api/v1/projects/${p.id}/plan/settings`, { method: "PUT", body: JSON.stringify(d) });
      onSaved(r.message);
    } catch (e) { onError(e.message); }
  };
  return (
    <details className="ba-box">
      <summary><b>Settings</b> <span className="small quiet">RACI {plan.raci_modes[s.raci].toLowerCase()} · {s.gates.length ? `gates at the end of ${s.gates.join(", ")}` : "no approval gates"}
        {s.roadmap_from || s.roadmap_to ? ` · roadmap ${s.roadmap_from || "…"} to ${s.roadmap_to || "…"}` : ""}</span></summary>
      {!plan.may_change && <p className="quiet small">The Project Admin or Lead Architect changes these.</p>}
      <fieldset disabled={!plan.may_change}>
        <label className="field">RACI <select value={d.raci} onChange={(e) => setD({ ...d, raci: e.target.value })} aria-label="How RACI is recorded">
          {Object.entries(plan.raci_modes).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <div className="field">Approval gates <span className="small quiet">a gated phase is complete only when each of its deliverables has an approved document</span>
          <div>{plan.phases.map((ph) => <label key={ph.code} className="choice"><input type="checkbox" checked={d.gates.includes(ph.code)} onChange={() => toggle(ph.code)} /> {ph.code}</label>)}</div></div>
        <div className="field">Roadmap period <span className="small quiet">any start and end; empty for all of it</span>
          <div><input type="date" value={d.roadmap_from} onChange={(e) => setD({ ...d, roadmap_from: e.target.value })} aria-label="Roadmap from" /> to{" "}
            <input type="date" value={d.roadmap_to} onChange={(e) => setD({ ...d, roadmap_to: e.target.value })} aria-label="Roadmap to" />{" "}
            <select value={d.roadmap_marks} onChange={(e) => setD({ ...d, roadmap_marks: e.target.value })} aria-label="Roadmap marks">
              <option value="month">by month</option><option value="quarter">by quarter</option><option value="year">by year</option></select></div></div>
        <button onClick={save}>Save the settings</button>
      </fieldset>
    </details>
  );
}

// the phases: when each is planned, how long, where it sits on the project's time line, its state and its gate
const DAY_MS = 86400000;
const ms = (d) => new Date(`${d}T00:00:00Z`).getTime();
function Phases({ p, plan, onSaved, onError }) {
  const [edit, setEdit] = useState({});
  const save = async (code) => {
    const v = edit[code] || {};
    try {
      const r = await apiFetch(`/api/v1/projects/${p.id}/plan/phases/${encodeURIComponent(code)}`, { method: "PUT", body: JSON.stringify(v) });
      setEdit({ ...edit, [code]: undefined }); onSaved(r.message);
    } catch (e) { onError(e.message); }
  };
  const planned = plan.phases.filter((x) => x.starts_on && x.ends_on);
  const lo = planned.length ? Math.min(...planned.map((x) => ms(x.starts_on))) : 0;
  const hi = planned.length ? Math.max(...planned.map((x) => ms(x.ends_on) + DAY_MS)) : 1;
  const today = Date.now();
  const pct = (t) => `${Math.max(0, Math.min(100, (100 * (t - lo)) / (hi - lo)))}%`;
  return (
    <section className="ba-box">
      <h4>The phases <span className="small quiet">{planned.length} of {plan.phases.length} planned</span></h4>
      <table className="grid-table small plan-phases">
        <thead><tr><th>Phase</th><th>Planned</th><th className="num">Days</th><th style={{ width: "30%" }}>Time line</th><th>State</th><th>Gate</th><th /></tr></thead>
        <tbody>{plan.phases.map((ph) => {
          const e = edit[ph.code];
          const days = ph.starts_on && ph.ends_on ? Math.round((ms(ph.ends_on) - ms(ph.starts_on)) / DAY_MS) + 1 : null;
          return (
            <tr key={ph.code}>
              <td><b style={{ whiteSpace: "nowrap" }}>{ph.code}</b> {ph.name.replace(/^Phase [A-Z-]+:\s*/, "")}</td>
              {e ? <td colSpan={3}>
                <input type="date" value={e.starts_on || ""} onChange={(x) => setEdit({ ...edit, [ph.code]: { ...e, starts_on: x.target.value } })} aria-label={`Start of ${ph.code}`} /> to{" "}
                <input type="date" value={e.ends_on || ""} onChange={(x) => setEdit({ ...edit, [ph.code]: { ...e, ends_on: x.target.value } })} aria-label={`End of ${ph.code}`} />{" "}
                <button onClick={() => save(ph.code)}>Save</button> <button className="linkish" onClick={() => setEdit({ ...edit, [ph.code]: undefined })}>Cancel</button>
                <span className="quiet"> (both empty: no plan)</span></td> : <>
                <td style={{ whiteSpace: "nowrap" }}>{ph.starts_on ? <>{fmtDate(ph.starts_on)} – {fmtDate(ph.ends_on)}</> : <span className="quiet">not planned</span>}</td>
                <td className="num">{days ?? ""}</td>
                <td>{ph.starts_on && <div className="plan-track" title={`${fmtDate(ph.starts_on)} to ${fmtDate(ph.ends_on)}`}>
                  <span className={`plan-bar${ph.complete ? " done" : ph.late ? " late" : ""}`}
                    style={{ left: pct(ms(ph.starts_on)), width: `calc(${pct(ms(ph.ends_on) + DAY_MS)} - ${pct(ms(ph.starts_on))})` }} />
                  {today > lo && today < hi && <span className="plan-today" style={{ left: pct(today) }} title="Today" />}</div>}</td>
              </>}
              <td>{ph.complete ? <span className="rag good">complete</span> : ph.late ? <span className="rag bad">late</span> : <span className="quiet">open</span>}</td>
              <td>{ph.gate ? (ph.waiting.length ? <span className="rag amber" title={`Waiting for approval:\n${ph.waiting.join("\n")}`}>{ph.waiting.length} to approve</span>
                : <span className="rag good">ready</span>) : <span className="quiet">–</span>}</td>
              <td>{plan.may_change && !e && <button className="linkish" onClick={() => setEdit({ ...edit, [ph.code]: { starts_on: ph.starts_on || "", ends_on: ph.ends_on || "" } })}>change</button>}</td>
            </tr>
          );
        })}</tbody></table>
    </section>
  );
}

function Milestones({ p, plan, onSaved, onError }) {
  const [d, setD] = useState({ name: "", due_on: "", phase: "" });
  const call = async (url, method, body) => {
    try { const r = await apiFetch(url, { method, body: body ? JSON.stringify(body) : undefined }); onSaved(r.message); return true; } catch (e) { onError(e.message); return false; }
  };
  const base = `/api/v1/projects/${p.id}/plan/milestones`;
  return (
    <section className="ba-box">
      <h4>Milestones</h4>
      {!plan.milestones.length ? <p className="quiet small">No milestones yet.</p>
        : <table className="grid-table small"><thead><tr><th>Milestone</th><th>Due</th><th>Phase</th><th>Done</th><th /></tr></thead>
          <tbody>{plan.milestones.map((m) => (
            <tr key={m.id}><td><b>{m.name}</b>{m.note && <div className="quiet">{m.note}</div>}</td>
              <td>{fmtDate(m.due_on)} {m.late && <span className="rag bad">late</span>}</td><td>{m.phase || <span className="quiet">–</span>}</td>
              <td><label><input type="checkbox" checked={!!m.done_at} disabled={!p.may_contribute} onChange={(e) => call(`${base}/${m.id}`, "PATCH", { done: e.target.checked })} />
                {m.done_at && <span className="quiet"> {m.done_by}, {fmtDate(m.done_at)}</span>}</label></td>
              <td>{plan.may_change && <button className="linkish" onClick={() => call(`${base}/${m.id}`, "DELETE")}>remove</button>}</td></tr>))}</tbody></table>}
      {p.may_contribute && <div className="toolbar small">
        <input value={d.name} placeholder="A new milestone" onChange={(e) => setD({ ...d, name: e.target.value })} aria-label="Milestone name" />
        <input type="date" value={d.due_on} onChange={(e) => setD({ ...d, due_on: e.target.value })} aria-label="Milestone date" />
        <select value={d.phase} onChange={(e) => setD({ ...d, phase: e.target.value })} aria-label="Milestone phase"><option value="">no phase</option>
          {plan.phases.map((ph) => <option key={ph.code} value={ph.code}>{ph.code}</option>)}</select>
        <button disabled={!d.name.trim() || !d.due_on} onClick={async () => { if (await call(base, "POST", d)) setD({ name: "", due_on: "", phase: "" }); }}>Add</button>
      </div>}
    </section>
  );
}

function Raci({ p, plan, onSaved, onError }) {
  const raci = plan.raci;
  const [open, setOpen] = useState(null);
  const [pick, setPick] = useState({});
  if (!raci || !raci.scope) return null;
  const word = { phase: "phase", deliverable: "deliverable", step: "step" }[raci.scope];
  const start = (r) => { setOpen(r.ref); setPick(Object.fromEntries(plan.people.map((u) => [u, r.people[u] || []]))); };
  const flip = (u, x) => setPick({ ...pick, [u]: (pick[u] || []).includes(x) ? pick[u].filter((y) => y !== x) : [...(pick[u] || []), x] });
  const save = async () => {
    try {
      const r = await apiFetch(`/api/v1/projects/${p.id}/plan/raci/${encodeURIComponent(open)}`, { method: "PUT", body: JSON.stringify({ people: pick }) });
      setOpen(null); onSaved(r.message);
    } catch (e) { onError(e.message); }
  };
  return (
    <section className="ba-box">
      <h4>RACI, per {word}</h4>
      <p className="small quiet">{Object.entries(plan.letters).map(([k, l]) => `${k}: ${l}`).join(" · ")}. One person is Accountable.
        {raci.no_accountable ? ` ${raci.no_accountable} with no one Accountable yet.` : ""}</p>
      <table className="grid-table small"><thead><tr><th>{word[0].toUpperCase() + word.slice(1)}</th><th>Who</th><th /></tr></thead>
        <tbody>{raci.rows.map((r) => (
          <tr key={r.ref}><td>{r.name}</td>
            <td>{open === r.ref
              ? plan.people.map((u) => <div key={u}>{u} {Object.keys(plan.letters).map((x) => <label key={x} className="choice"><input type="checkbox" checked={(pick[u] || []).includes(x)} onChange={() => flip(u, x)} />{x}</label>)}</div>)
              : Object.entries(r.people).map(([u, ls]) => <span key={u} className="chip small">{u}: {ls.join("")}</span>)}
              {open !== r.ref && !Object.keys(r.people).length && <span className="quiet">–</span>}</td>
            <td>{plan.may_change && (open === r.ref ? <><button onClick={save}>Save</button> <button className="linkish" onClick={() => setOpen(null)}>Cancel</button></>
              : <button className="linkish" onClick={() => start(r)}>change</button>)}</td></tr>))}</tbody></table>
    </section>
  );
}

function Status({ p, plan, onSaved, onError }) {
  const [d, setD] = useState({ rag: "green", summary: "", next_steps: "" });
  const add = async () => {
    try {
      const r = await apiFetch(`/api/v1/projects/${p.id}/plan/status`, { method: "POST", body: JSON.stringify(d) });
      setD({ rag: "green", summary: "", next_steps: "" }); onSaved(r.message);
    } catch (e) { onError(e.message); }
  };
  return (
    <section className="ba-box">
      <h4>Status</h4>
      {p.may_contribute && <div className="small">
        <select value={d.rag} onChange={(e) => setD({ ...d, rag: e.target.value })} aria-label="Status"><option value="green">Green</option><option value="amber">Amber</option><option value="red">Red</option></select>{" "}
        <input value={d.summary} placeholder="How the project stands" onChange={(e) => setD({ ...d, summary: e.target.value })} aria-label="Status summary" size={50} />{" "}
        <input value={d.next_steps} placeholder="Next steps" onChange={(e) => setD({ ...d, next_steps: e.target.value })} aria-label="Next steps" size={30} />{" "}
        <button disabled={!d.summary.trim()} onClick={add}>Report</button></div>}
      {!plan.status.length ? <p className="quiet small">No status reported yet.</p>
        : <ul className="plain small">{plan.status.map((s, i) => (
          <li key={i}><span className={`rag ${RAG_CLASS[s.rag]}`}>{s.rag}</span> {s.summary}{s.next_steps && <span className="quiet"> · next: {s.next_steps}</span>}
            <span className="quiet"> · {s.by_user}, {fmtDateTime(s.at)}</span></li>))}</ul>}
    </section>
  );
}

export default function ProjectPlanTab({ p }) {
  const { data: plan, error } = useApi(`/api/v1/projects/${p.id}/plan`);
  const [msg, setMsg] = useState(null);
  if (error) return <p className="status bad">{error}</p>;
  if (!plan) return <p>Loading the plan...</p>;
  const ok = (m) => { setMsg({ ok: true, m }); refreshAll(); };
  const bad = (m) => setMsg({ ok: false, m });
  const s = plan.settings;
  return (
    <div className="project-plan">
      <p className="quiet small">The project's plan (TOGAF Series Guide: Project Management and the ADM): its phases, milestones, who is responsible and how it stands.
        {plan.late ? <> <span className="rag bad">{plan.late} late</span></> : null}</p>
      {msg && <p className={`status ${msg.ok ? "good" : "bad"}`}>{msg.m}</p>}
      <Settings key={JSON.stringify(s)} p={p} plan={plan} onSaved={ok} onError={bad} />
      <Phases p={p} plan={plan} onSaved={ok} onError={bad} />
      <Milestones p={p} plan={plan} onSaved={ok} onError={bad} />
      <Raci p={p} plan={plan} onSaved={ok} onError={bad} />
      <Status p={p} plan={plan} onSaved={ok} onError={bad} />
      {p.home_model && <section className="ba-box"><h4>Roadmap of the primary working model</h4>
        <Roadmap model={p.home_model} from={s.roadmap_from} to={s.roadmap_to} marks={s.roadmap_marks} /></section>}
    </div>
  );
}
