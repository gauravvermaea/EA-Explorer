// Monte Carlo studies (Release 14.7; D957, D962): a project's Monte Carlo tab. Ranges instead of single numbers, run
// thousands of times by EA Explorer's own engine (eax/monte_carlo.py): roadmap confidence, an option's business case,
// risk exposure, scenario planning with chances. The ranges are typed here or drafted by the person's AI over MCP
// (each input says who set it and where it came from); every run is kept with the inputs and seed it used.
import { useEffect, useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { fmtDateTime, fmtNumber } from "./fmt";
import { refreshAll, useApi } from "./ModelViews";

const pct = (x) => `${Math.round((x || 0) * 100)}%`;
const num = (x) => (x == null || x === "" ? "" : fmtNumber(Number(x), Math.abs(Number(x)) >= 100 ? 0 : 1));
const toNum = (v) => (v === "" || v == null ? "" : Number(v));

// the columns each kind's inputs have
const COLUMNS = {
  roadmap: [["name", "Work package"], ["low", "Low"], ["likely", "Most likely"], ["high", "High"], ["shape", "Shape"], ["after", "Waits for"], ["source", "Where from"]],
  business_case: [["name", "Line"], ["side", "Benefit or cost"], ["low", "Low"], ["likely", "Most likely"], ["high", "High"], ["shape", "Shape"], ["source", "Where from"]],
  risk: [["name", "Risk"], ["chance", "Chance a year (0–1)"], ["likelihood", "or Likelihood 1–5"], ["low", "Loss low"], ["likely", "likely"], ["high", "high"],
    ["impact", "or Impact 1–5"], ["chance_after", "After controls (0–1)"], ["likelihood_after", "or Likelihood after"], ["source", "Where from"]],
  scenarios: [["option", "Option"], ["future", "Future"], ["low", "Low score"], ["likely", "Most likely"], ["high", "High"], ["shape", "Shape"], ["source", "Where from"]],
};
const ADD = { roadmap: "+ Add a work package", business_case: "+ Add a line", risk: "+ Add a risk", scenarios: "+ Add a score" };
const NUMERIC = new Set(["low", "likely", "high", "chance", "likelihood", "impact", "chance_after", "likelihood_after"]);
const blank = (kind) => Object.fromEntries(COLUMNS[kind].map(([k]) => [k, k === "after" ? [] : k === "side" ? "cost" : k === "shape" ? "pert" : ""]));

function clean(kind, rows) {
  return rows.filter((r) => (kind === "scenarios" ? r.option && r.future : r.name)).map((r) => {
    const out = {};
    for (const [k] of COLUMNS[kind]) {
      if (r[k] === "" || r[k] == null) continue;
      out[k] = NUMERIC.has(k) ? toNum(r[k]) : r[k];
    }
    return out;
  });
}

// ---------------------------------------------------------------- pictures: the S-curve, the histogram, the tornado
function SCurve({ points, unit }) {
  if (!points?.length) return null;
  const lo = points[0].value, hi = points[points.length - 1].value, w = 420, h = 160, pad = 32;
  const x = (v) => pad + ((v - lo) / (hi - lo || 1)) * (w - 2 * pad);
  const y = (c) => h - pad + 8 - c * (h - pad - 8);
  return (
    <figure className="mc-figure">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="The chance of meeting each result (the S-curve)">
        <line x1={pad} y1={y(0)} x2={w - pad} y2={y(0)} stroke="currentColor" opacity="0.3" />
        {[0.5, 0.8].map((c) => <line key={c} x1={pad} y1={y(c)} x2={w - pad} y2={y(c)} stroke="currentColor" opacity="0.15" strokeDasharray="3 3" />)}
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={points.map((p) => `${x(p.value)},${y(p.chance)}`).join(" ")} />
        <text x={pad} y={h - 6} fontSize="10">{num(lo)}</text>
        <text x={w - pad} y={h - 6} fontSize="10" textAnchor="end">{num(hi)} {unit}</text>
        <text x={4} y={y(0.8) + 3} fontSize="10">80%</text><text x={4} y={y(0.5) + 3} fontSize="10">50%</text>
      </svg>
      <figcaption className="small quiet">The chance of meeting each result: read across from a chance to the value.</figcaption>
    </figure>
  );
}

function Histogram({ bins }) {
  if (!bins?.length) return null;
  const top = Math.max(...bins.map((b) => b.runs)) || 1, w = 420, h = 110, bw = w / bins.length;
  return (
    <figure className="mc-figure">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="How the runs fell">
        {bins.map((b, i) => <rect key={i} x={i * bw + 1} y={h - (b.runs / top) * (h - 10)} width={bw - 2} height={(b.runs / top) * (h - 10)}
          fill="currentColor" opacity="0.45"><title>{`${num(b.from)} to ${num(b.to)}: ${b.runs} runs`}</title></rect>)}
      </svg>
      <figcaption className="small quiet">How the runs fell, from the lowest result to the highest.</figcaption>
    </figure>
  );
}

function Drivers({ drivers }) {
  const shown = (drivers || []).filter((d) => d.strength > 0).slice(0, 8);
  if (!shown.length) return null;
  return (
    <section><h4>What drives the result most</h4>
      <table className="grid-table small"><tbody>{shown.map((d) => (
        <tr key={d.input}><td>{d.input}</td><td style={{ width: "50%" }}>
          <span className="mc-bar" style={{ display: "inline-block", width: `${Math.round(d.strength * 100)}%`, background: "currentColor", opacity: 0.4, height: "0.8em" }} />
        </td><td className="num">{d.strength.toFixed(2)}</td></tr>))}</tbody></table>
    </section>
  );
}

function Figures({ r, unit, cur }) {
  if (!r) return null;
  const u = unit || cur || "";
  return (
    <table className="grid-table small mc-figures">
      <thead><tr>{["Lowest", "P10", "P50 (half the runs)", "P80", "P90", "Highest", "Mean"].map((t) => <th key={t} scope="col" className="num">{t}</th>)}</tr></thead>
      <tbody><tr>{[r.low, r.p10, r.p50, r.p80, r.p90, r.high, r.mean].map((v, i) => <td key={i} className="num">{num(v)}{u && i === 2 ? ` ${u}` : ""}</td>)}</tr></tbody>
    </table>
  );
}

function Result({ s, run, project }) {
  if (!run) return <p className="quiet small">Not run yet: save the inputs, then <b>Run</b>.</p>;
  const res = run.result || {};
  const r = res.result;
  return (
    <section className="mc-result">
      <h3>Run {run.number} <span className="quiet small">{fmtDateTime(run.run_at)} · by {run.run_by} · {fmtNumber(run.runs, 0)} runs · seed {run.seed}</span></h3>
      <ul className="mc-words">{(res.in_words || []).map((w, i) => <li key={i}>{w}</li>)}</ul>
      {r && <><Figures r={r} unit={s.kind === "roadmap" ? s.unit : ""} cur={s.kind !== "roadmap" ? s.currency : ""} />
        <div className="mc-pictures"><SCurve points={r.s_curve} unit={s.kind === "roadmap" ? s.unit : s.currency} /><Histogram bins={r.histogram} /></div>
        <Drivers drivers={r.drivers} /></>}
      {r?.critical && (
        <section><h4>On the critical path</h4>
          <table className="grid-table small"><tbody>{Object.entries(r.critical).map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{pct(v)} of runs</td></tr>)}</tbody></table>
        </section>)}
      {res.milestones && (
        <section><h4>Milestones</h4>
          <table className="grid-table small"><thead><tr><th scope="col">Milestone</th><th scope="col" className="num">P50</th><th scope="col" className="num">P80</th>
            <th scope="col" className="num">P90</th><th scope="col" className="num">By the date</th></tr></thead>
          <tbody>{res.milestones.map((m) => <tr key={m.name}><td>{m.name}</td><td className="num">{num(m.p50)}</td><td className="num">{num(m.p80)}</td>
            <td className="num">{num(m.p90)}</td><td className="num">{m.by != null ? `${pct(m.chance)} by ${num(m.by)}` : ""}</td></tr>)}</tbody></table>
        </section>)}
      {res.after && (<section><h4>After controls</h4><Figures r={res.after} cur={s.currency} /></section>)}
      {res.amounts?.length > 0 && (
        <section><h4>The chance a year's losses pass an amount</h4>
          <table className="grid-table small"><thead><tr><th scope="col">Amount</th><th scope="col" className="num">Before controls</th><th scope="col" className="num">After</th></tr></thead>
            <tbody>{res.amounts.map((a) => <tr key={a.amount}><td>{s.currency} {num(a.amount)}</td><td className="num">{pct(a.before)}</td><td className="num">{a.after != null ? pct(a.after) : ""}</td></tr>)}</tbody></table>
        </section>)}
      {res.across && (
        <section><h4>The chance each option is best</h4>
          <table className="grid-table small"><thead><tr><th scope="col">Option</th><th scope="col" className="num">{res.weighted ? "Weighted" : "Across the futures"}</th>
            {res.futures.map((f) => <th key={f} scope="col" className="num">{f}</th>)}</tr></thead>
            <tbody>{res.options.map((o) => <tr key={o}><td>{o}</td><td className="num">{pct(res.across[o])}</td>
              {res.futures.map((f) => <td key={f} className="num">{pct(res.in_each[f][o])}</td>)}</tr>)}</tbody></table>
        </section>)}
      <p className="small">
        <button className="linkish" onClick={() => apiDownload(`/api/v1/projects/${project}/monte-carlo/${s.id}/runs/${run.number}/csv`, `${s.name} run ${run.number}.csv`)}>⬇ The figures as CSV</button>
        {" · "}<span className="quiet">The working: {fmtNumber(run.runs, 0)} runs, seed {run.seed}, inputs as they were (digest {String(run.digest).slice(0, 12)}): the same inputs and seed give the same answer.</span>
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- editing a study
function InputsTable({ kind, rows, setRows, may }) {
  const cols = COLUMNS[kind];
  const names = rows.map((r) => r.name).filter(Boolean);
  const set = (i, k, v) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="table-scroll">
      <table className="grid-table small mc-inputs">
        <thead><tr>{cols.map(([k, l]) => <th key={k} scope="col">{l}</th>)}<th scope="col">Set by</th>{may && <th scope="col" />}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i}>{cols.map(([k, l]) => (
            <td key={k}>{k === "shape" ? <select aria-label={l} disabled={!may} value={r.shape || "pert"} onChange={(e) => set(i, k, e.target.value)}><option value="pert">PERT</option><option value="triangular">triangular</option></select>
              : k === "side" ? <select aria-label={l} disabled={!may} value={r.side || "cost"} onChange={(e) => set(i, k, e.target.value)}><option value="cost">cost</option><option value="benefit">benefit</option></select>
                : k === "after" ? <select aria-label={l} multiple disabled={!may} value={r.after || []} size={Math.min(3, Math.max(1, names.length - 1))}
                  onChange={(e) => set(i, k, [...e.target.selectedOptions].map((o) => o.value))}>{names.filter((n) => n !== r.name).map((n) => <option key={n}>{n}</option>)}</select>
                  : <input aria-label={l} disabled={!may} value={r[k] ?? ""} type={NUMERIC.has(k) ? "number" : "text"} step="any" size={NUMERIC.has(k) ? 8 : 18}
                    onChange={(e) => set(i, k, e.target.value)} />}</td>))}
            <td className="quiet">{r.set_by ? `${r.set_by}${r.by === "ai" ? " (AI)" : ""}` : "new"}</td>
            {may && <td><button className="linkish" title="Remove this input" onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button></td>}
          </tr>))}</tbody>
      </table>
      {may && <button onClick={() => setRows([...rows, blank(kind)])}>{ADD[kind]}</button>}
    </div>
  );
}

function Groups({ groups, setGroups, names, may, strengths }) {
  const set = (i, k, v) => setGroups(groups.map((g, j) => (j === i ? { ...g, [k]: v } : g)));
  return (
    <section><h4>Inputs that move together</h4>
      <p className="small quiet">One supplier's work, costs in one currency: they tend to go wrong together. Leave them apart and the result looks safer than it is.</p>
      {groups.map((g, i) => (
        <div key={i} className="mc-group">
          <input aria-label="Group name" disabled={!may} value={g.name} placeholder="Group name" onChange={(e) => set(i, "name", e.target.value)} />
          <select aria-label="Strength" disabled={!may} value={g.strength} onChange={(e) => set(i, "strength", e.target.value)}>{strengths.map((st) => <option key={st}>{st}</option>)}</select>
          <select aria-label="Members" multiple disabled={!may} value={g.members} size={Math.min(5, names.length)} onChange={(e) => set(i, "members", [...e.target.selectedOptions].map((o) => o.value))}>
            {names.map((n) => <option key={n}>{n}</option>)}</select>
          {may && <button className="linkish" onClick={() => setGroups(groups.filter((_, j) => j !== i))}>✕</button>}
        </div>))}
      {may && names.length > 1 && <button onClick={() => setGroups([...groups, { name: "", members: [], strength: "medium" }])}>+ A group</button>}
    </section>
  );
}

function Settings({ kind, settings, setSettings, names, futures, may, unit }) {
  if (kind === "roadmap") {
    const ms = settings.milestones || [];
    const setM = (i, k, v) => setSettings({ ...settings, milestones: ms.map((m, j) => (j === i ? { ...m, [k]: v } : m)) });
    return (
      <section><h4>The date that matters</h4>
        <label>Target ({unit} from the start) <input type="number" step="any" disabled={!may} value={settings.target ?? ""} onChange={(e) => setSettings({ ...settings, target: e.target.value })} /></label>
        <p className="small quiet">Milestones: reached when all their work packages have ended.</p>
        {ms.map((m, i) => (
          <div key={i} className="mc-group">
            <input aria-label="Milestone" disabled={!may} value={m.name} placeholder="Milestone" onChange={(e) => setM(i, "name", e.target.value)} />
            <select aria-label="Its work packages" multiple disabled={!may} value={m.packages || []} size={Math.min(4, names.length)} onChange={(e) => setM(i, "packages", [...e.target.selectedOptions].map((o) => o.value))}>
              {names.map((n) => <option key={n}>{n}</option>)}</select>
            <label>by <input type="number" step="any" size={6} disabled={!may} value={m.by ?? ""} onChange={(e) => setM(i, "by", e.target.value)} /></label>
            {may && <button className="linkish" onClick={() => setSettings({ ...settings, milestones: ms.filter((_, j) => j !== i) })}>✕</button>}
          </div>))}
        {may && <button onClick={() => setSettings({ ...settings, milestones: [...ms, { name: "", packages: [], by: "" }] })}>+ A milestone</button>}
      </section>);
  }
  if (kind === "risk") {
    return (
      <section><h4>Amounts to test</h4>
        <label>The chance a year's losses pass (comma-separated) <input disabled={!may} value={(settings.amounts || []).join(", ")}
          onChange={(e) => setSettings({ ...settings, amounts: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} /></label>
      </section>);
  }
  if (kind === "scenarios") {
    const w = settings.weights || {};
    return (
      <section><h4>How likely each future is (optional)</h4>
        <p className="small quiet">Leave them empty to compare the options across all the futures together.</p>
        {futures.map((f) => <label key={f} className="mc-weight">{f} <input type="number" step="any" size={5} disabled={!may} value={w[f] ?? ""}
          onChange={(e) => setSettings({ ...settings, weights: { ...w, [f]: e.target.value } })} /></label>)}
      </section>);
  }
  return null;
}

function settingsOut(kind, s) {
  if (kind === "roadmap") {
    return { ...(s.target !== "" && s.target != null ? { target: Number(s.target) } : {}),
      milestones: (s.milestones || []).filter((m) => m.name).map((m) => ({ name: m.name, packages: m.packages || [], ...(m.by !== "" && m.by != null ? { by: Number(m.by) } : {}) })) };
  }
  if (kind === "risk") return { amounts: (s.amounts || []).map(Number).filter((x) => !Number.isNaN(x)) };
  if (kind === "scenarios") {
    const w = Object.fromEntries(Object.entries(s.weights || {}).filter(([, v]) => v !== "" && v != null).map(([k, v]) => [k, Number(v)]));
    return Object.keys(w).length ? { weights: w } : {};
  }
  return {};
}

function StudyPage({ project, studyId, base }) {
  const { data: s, error } = useApi(`/api/v1/projects/${project}/monte-carlo/${studyId}`);
  const [rows, setRows] = useState([]);
  const [groups, setGroups] = useState([]);
  const [settings, setSettings] = useState({});
  const [runs, setRuns] = useState(10000);
  const [view, setView] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!s) return;
    setRows((s.inputs || []).map((i) => ({ ...blank(s.kind), ...i })));
    setGroups(s.groups || []);
    setSettings(s.settings || {});
    setRuns(s.runs);
    setView(null);
  }, [s]);
  if (error) return <p className="status bad">{error}</p>;
  if (!s) return <p>Loading…</p>;
  const may = base?.may_change;
  const names = rows.map((r) => (s.kind === "scenarios" ? (r.option && r.future ? `${r.option} in ${r.future}` : "") : r.name)).filter(Boolean);
  const futures = [...new Set(rows.map((r) => r.future).filter(Boolean))];
  const act = async (fn, done) => {
    setBusy(true); setMsg("");
    try { const out = await fn(); setMsg(done(out)); refreshAll(); } catch (e) { setMsg(e.message); } finally { setBusy(false); }
  };
  const save = () => act(() => apiFetch(`/api/v1/projects/${project}/monte-carlo/${s.id}`, { method: "PUT",
    body: JSON.stringify({ inputs: clean(s.kind, rows), groups: groups.filter((g) => g.name), settings: settingsOut(s.kind, settings), runs: Number(runs) }) }), (o) => o.message);
  const run = () => act(() => apiFetch(`/api/v1/projects/${project}/monte-carlo/${s.id}/run`, { method: "POST", body: JSON.stringify({ runs: Number(runs) }) }), (o) => o.message);
  const remove = () => {
    if (!window.confirm(`Delete the study ${s.name} and its ${s.run_count} run(s)? This cannot be undone.`)) return;
    act(() => apiFetch(`/api/v1/projects/${project}/monte-carlo/${s.id}`, { method: "DELETE" }), (o) => { window.location.hash = `#/projects/${project}/montecarlo`; return o.message; });
  };
  const openRun = async (n) => { try { setView(await apiFetch(`/api/v1/projects/${project}/monte-carlo/${s.id}/runs/${n}`)); } catch (e) { setMsg(e.message); } };
  const shown = view || s.latest;
  return (
    <div className="mc-study">
      <p><a href={`#/projects/${project}/montecarlo`}>← All Monte Carlo studies</a></p>
      <h3>{s.name} <span className="chip on">{s.kind_name}</span></h3>
      {s.question && <p><b>{s.question}</b></p>}
      <p className="small quiet">{s.kind === "roadmap" ? `Durations in ${s.unit}` : s.currency ? `Amounts in ${s.currency}` : ""} · changed {fmtDateTime(s.updated_at)} by {s.updated_by}</p>
      {s.changed_since && <p className="status warn small">The inputs changed since run {s.latest.number}: run it again to see their effect.</p>}
      <Result s={s} run={shown} project={project} />
      {view && <p className="small"><button className="linkish" onClick={() => setView(null)}>Back to the latest run</button></p>}
      <h3>The inputs</h3>
      <p className="small quiet">Three numbers for each: low, most likely, high{s.kind === "risk" ? "; a risk's chance in a year and its loss, or its Likelihood and Impact by the organisation's risk scale" : ""}. Your AI can draft them over MCP (mc_save); each says who set it.</p>
      <InputsTable kind={s.kind} rows={rows} setRows={setRows} may={may} />
      <Groups groups={groups} setGroups={setGroups} names={names} may={may} strengths={base?.strengths || ["weak", "medium", "strong"]} />
      <Settings kind={s.kind} settings={settings} setSettings={setSettings} names={names} futures={futures} may={may} unit={s.unit} />
      {may && (
        <div className="toolbar">
          <button disabled={busy} onClick={save}>Save</button>
          <label>Runs <input type="number" min="100" max="100000" step="100" value={runs} onChange={(e) => setRuns(e.target.value)} /></label>
          <button className="primary" disabled={busy} onClick={run}>▶ Run</button>
          <button disabled={busy} onClick={remove}>Delete the study…</button>
        </div>)}
      {msg && <p className="small">{msg}</p>}
      {(s.runs_list || []).length > 1 && (
        <section><h4>Earlier runs</h4>
          <ul className="small">{s.runs_list.map((r) => <li key={r.number}><button className="linkish" onClick={() => openRun(r.number)}>Run {r.number}</button> · {fmtDateTime(r.run_at)} · {r.run_by} · {(r.in_words || [])[0]}</li>)}</ul>
        </section>)}
    </div>
  );
}

// ---------------------------------------------------------------- the risk scale and the list of studies
function RiskScale({ scale, may }) {
  const [edit, setEdit] = useState(null);
  const [msg, setMsg] = useState("");
  const save = async () => {
    try {
      const out = await apiFetch("/api/v1/monte-carlo/risk-scale", { method: "PUT", body: JSON.stringify({ currency: edit.currency,
        likelihood: Object.fromEntries(Object.entries(edit.likelihood).map(([k, v]) => [k, Number(v)])),
        impact: Object.fromEntries(Object.entries(edit.impact).map(([k, v]) => [k, v.map(Number)])) }) });
      setMsg(out.message); setEdit(null); refreshAll();
    } catch (e) { setMsg(e.message); }
  };
  const s = edit || scale;
  return (
    <details className="mc-scale"><summary>The organisation's risk scale{scale.default ? " (the defaults: set it for your organisation)" : ` (set by ${scale.set_by})`}</summary>
      <table className="grid-table small"><thead><tr><th scope="col">Level</th><th scope="col" className="num">Likelihood: chance a year</th><th scope="col">Impact: loss low, likely, high {s.currency}</th></tr></thead>
        <tbody>{["1", "2", "3", "4", "5"].map((l) => (
          <tr key={l}><td>{l}</td>
            <td className="num">{edit ? <input type="number" step="any" aria-label={`Likelihood ${l}`} value={edit.likelihood[l]} onChange={(e) => setEdit({ ...edit, likelihood: { ...edit.likelihood, [l]: e.target.value } })} /> : pct(s.likelihood[l])}</td>
            <td>{edit ? edit.impact[l].map((v, i) => <input key={i} type="number" step="any" size={10} aria-label={`Impact ${l} ${["low", "likely", "high"][i]}`} value={v}
              onChange={(e) => setEdit({ ...edit, impact: { ...edit.impact, [l]: edit.impact[l].map((x, j) => (j === i ? e.target.value : x)) } })} />)
              : s.impact[l].map(num).join(" · ")}</td></tr>))}</tbody></table>
      {may && !edit && <button onClick={() => setEdit({ likelihood: { ...scale.likelihood }, impact: { ...scale.impact }, currency: scale.currency || "" })}>✎ Change the scale</button>}
      {edit && <><label>Currency <input size={5} value={edit.currency} onChange={(e) => setEdit({ ...edit, currency: e.target.value })} /></label>
        <button className="primary" onClick={save}>Save the scale</button><button onClick={() => setEdit(null)}>Cancel</button></>}
      {msg && <p className="small">{msg}</p>}
    </details>
  );
}

function NewStudy({ project, kinds, units }) {
  const [f, setF] = useState({ name: "", kind: "roadmap", question: "", currency: "", unit: "weeks" });
  const [msg, setMsg] = useState("");
  const make = async () => {
    try {
      const out = await apiFetch(`/api/v1/projects/${project}/monte-carlo`, { method: "POST", body: JSON.stringify(f) });
      refreshAll(); window.location.hash = `#/projects/${project}/montecarlo/${out.study.id}`;
    } catch (e) { setMsg(e.message); }
  };
  return (
    <details className="mc-new"><summary>+ A new study</summary>
      <label>Name <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
      <label>What it answers <select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{kinds.map((k) => <option key={k.kind} value={k.kind}>{k.name}</option>)}</select></label>
      <p className="small quiet">{kinds.find((k) => k.kind === f.kind)?.answers}</p>
      <label>The question <input size={50} value={f.question} onChange={(e) => setF({ ...f, question: e.target.value })} /></label>
      {f.kind === "roadmap" ? <label>Durations in <select value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}>{units.map((u) => <option key={u}>{u}</option>)}</select></label>
        : <label>Currency <input size={5} value={f.currency} placeholder="ZAR" onChange={(e) => setF({ ...f, currency: e.target.value })} /></label>}
      <button className="primary" disabled={!f.name.trim()} onClick={make}>Make the study</button>
      {msg && <p className="status bad small">{msg}</p>}
    </details>
  );
}

export default function MonteCarloTab({ p, sub }) {
  const project = p.id;
  const { data, error } = useApi(`/api/v1/projects/${project}/monte-carlo`);
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading…</p>;
  if (sub) return <StudyPage project={project} studyId={sub} base={data} />;
  return (
    <div className="mc-tab">
      <p className="small quiet">Ranges instead of single numbers, run thousands of times by EA Explorer: how likely a date or an amount is, and what drives it.
        Type the ranges here, or ask your AI to draft them from the project's documents and models (the prompt monte_carlo_study).</p>
      {data.studies.length === 0 ? <p>No study yet.</p> : (
        <table className="grid-table">
          <thead><tr><th scope="col">Study</th><th scope="col">What it answers</th><th scope="col" className="num">Inputs</th><th scope="col">Latest run</th><th scope="col">Changed</th></tr></thead>
          <tbody>{data.studies.map((s) => (
            <tr key={s.id}><td><a href={`#/projects/${project}/montecarlo/${s.id}`}>{s.name}</a></td><td>{s.kind_name}</td><td className="num">{s.inputs_count}</td>
              <td className="small">{s.latest ? `Run ${s.latest.number}: ${(s.latest.in_words || [])[0] || ""}` : <span className="quiet">not run yet</span>}</td>
              <td className="small">{fmtDateTime(s.updated_at)}</td></tr>))}</tbody>
        </table>)}
      {data.may_change && <NewStudy project={project} kinds={data.kinds} units={data.units} />}
      <RiskScale scale={data.risk_scale} may={data.may_set_scale} />
    </div>
  );
}
