// Scenario planning and game theory (Release 10; D788, D818, D857): a project's Scenario planning tab, read only.
// The wizard runs through the person's AI over MCP (the prompt scenario_planning_wizard); this tab shows what it made:
// the version shown (the newest finished one) with its question, the driving forces, the futures and their signposts
// (those due at this review marked), the players and their games worked out, the options scored across the futures
// (the most robust and the least regret), and the recommendation; earlier versions a click away; the draft, if any.
import { useState } from "react";
import { fmtDateTime, fmtNumber } from "./fmt";
import { useApi } from "./ModelViews";

const val = (v) => {
  if (v == null) return "";
  if (typeof v === "number") return String(v);
  if (typeof v === "object") {
    if (v.money != null) return `${v.currency ? `${v.currency} ` : ""}${fmtNumber(v.money, 0)}`;
    if (v.words) return `${v.words} (${v.score})`;
    if (v.score != null) return String(v.score);
  }
  return String(v);
};
const named = (prof) => Object.entries(prof || {}).map(([pl, o]) => `${pl}: ${o}`).join(", ");

function Said({ lines }) {
  if (!lines || !lines.length) return null;
  return <ul className="small sp-said">{lines.map((l, i) => <li key={i}>{l}</li>)}</ul>;
}

function Game({ g, w }) {
  return (
    <section className="sp-game">
      <h4>{g.name} <span className="quiet small">{g.kind === "sequential" ? "moves in turn" : "moves at once"} · {(g.players || []).join(", ")}</span></h4>
      {w?.error ? <p className="status bad small">{w.error}</p> : <Said lines={w?.in_words} />}
      {g.kind !== "sequential" && w?.outcomes && (
        <details><summary className="small">The payoff table ({w.outcomes.length} outcomes{w.how_compared ? `, compared ${w.how_compared}` : ""})</summary>
          <table className="grid-table small">
            <thead><tr><th scope="col">Outcome</th>{(g.players || []).map((pl) => <th scope="col" key={pl} className="num">{pl}</th>)}<th scope="col">Stable</th></tr></thead>
            <tbody>{w.outcomes.map((o, i) => (
              <tr key={i}><td>{named(o.options)}</td>{(g.players || []).map((pl) => <td key={pl} className="num">{o.values[pl]}</td>)}
                <td>{(w.stable || []).some((s) => named(s) === named(o.options)) ? "✓" : ""}</td></tr>))}</tbody>
          </table></details>)}
      {g.kind === "sequential" && w?.plan && (
        <details><summary className="small">Worked back from the end ({w.plan.length} choices)</summary>
          <ul className="small">{w.plan.map((s, i) => <li key={i}>After {s.after.join(" then ") || "the start"}: {s.player} chooses <b>{s.chooses}</b> (gets {s.gets})</li>)}</ul>
        </details>)}
    </section>
  );
}

function Study({ r, signposts }) {
  const res = r.results || {};
  const opt = res.options;
  const futures = (r.futures || []).map((f) => f.name);
  return (
    <div className="sp-study">
      <p><b>{r.question}</b></p>
      <p className="quiet small">Version {r.version} · {r.template_name} · {r.status === "done" ? `finished ${fmtDateTime(r.finished_at)}` : "draft"} · by {r.created_by}</p>
      {r.recommendation && (
        <section className="sp-reco"><h3>Recommendation{r.recommended ? `: ${r.recommended}` : ""}</h3>
          {r.recommendation.split(/\n\s*\n/).map((para, i) => <p key={i}>{para}</p>)}</section>)}
      {(r.forces || []).length > 0 && (
        <section><h3>Driving forces</h3>
          <table className="grid-table small"><thead><tr><th scope="col">Force</th><th scope="col">Kind</th><th scope="col" className="num">Impact</th>
            <th scope="col" className="num">Uncertainty</th><th scope="col">Note</th></tr></thead>
            <tbody>{r.forces.map((f) => <tr key={f.name}><td>{f.name}</td><td>{f.kind}</td><td className="num">{f.impact}</td>
              <td className="num">{f.uncertainty}</td><td>{f.note}</td></tr>)}</tbody></table>
          {(r.uncertainties || []).length > 0 && <p className="small">Critical uncertainties: {r.uncertainties.map((u) => `${u.name} (${u.low} … ${u.high})`).join("; ")}</p>}
        </section>)}
      {(r.futures || []).length > 0 && (
        <section><h3>The futures</h3>
          <div className="sp-futures">{r.futures.map((f) => (
            <article key={f.name} className="card sp-future"><h4>{f.name}</h4>
              {f.when && <p className="quiet small">{f.when}</p>}
              {Object.keys(f.positions || {}).length > 0 && <p className="quiet small">{Object.entries(f.positions).map(([u, p]) => `${u}: ${p}`).join(" · ")}</p>}
              <p className="small">{f.story}</p>
              {(f.true || []).length > 0 && <ul className="small">{f.true.map((t, i) => <li key={i}>{t}</li>)}</ul>}
              {f.model && <p className="small">Answered by the model <b>{f.model}</b></p>}
            </article>))}</div>
        </section>)}
      {(signposts || r.signposts || []).length > 0 && (
        <section><h3>Signposts</h3>
          <p className="quiet small">The early signs that a future is coming true. At each project review, ask your AI to mark each as seen or not
            (<code>sp_mark_signposts</code>); one not marked for 90 days is due again.</p>
          <table className="grid-table small"><thead><tr><th scope="col">Ref</th><th scope="col">Future</th><th scope="col">Sign</th><th scope="col">Watch</th>
            <th scope="col">Level</th><th scope="col">Last marked</th></tr></thead>
            <tbody>{(signposts || r.signposts).map((s) => (
              <tr key={s.ref} className={s.due ? "sp-due" : ""}><td>{s.ref}</td><td>{s.future}</td><td>{s.sign}</td><td>{s.watch}</td><td>{s.level}</td>
                <td>{s.last ? `${s.last.seen ? "seen" : "not seen"} · ${s.last.by} · ${fmtDateTime(s.last.at)}${s.last.note ? ` · ${s.last.note}` : ""}` : ""}
                  {s.due && <span className="status warn small"> due at this review</span>}</td></tr>))}</tbody></table>
        </section>)}
      {(r.options || []).length > 0 && (
        <section><h3>The options across the futures</h3>
          {opt?.error ? <p className="status bad small">{opt.error}</p> : opt && (<>
            <table className="grid-table small"><thead><tr><th scope="col">Option</th>{futures.map((f) => <th scope="col" key={f} className="num">{f}</th>)}
              <th scope="col" className="num">Worst case</th><th scope="col" className="num">Regret</th></tr></thead>
              <tbody>{opt.table.map((row) => (
                <tr key={row.option} className={(opt.robust || []).includes(row.option) ? "sp-best" : ""}>
                  <td>{row.option}{(r.options.find((o) => o.name === row.option) || {}).model ? <span className="quiet"> · {(r.options.find((o) => o.name === row.option)).model}</span> : null}</td>
                  {futures.map((f) => <td key={f} className="num" title={val((r.scores || []).find((s) => s.option === row.option && s.future === f)?.value)}>{row[f]}</td>)}
                  <td className="num">{row.worst}</td><td className="num">{row.regret}</td></tr>))}</tbody></table>
            <p className="quiet small">Compared {opt.how_compared}. Higher is better.</p>
            <Said lines={opt.in_words} /></>)}
          <Said lines={res.players_answers} />
        </section>)}
      {(r.players || []).length > 0 && (
        <section><h3>The players</h3>
          <ul className="small">{r.players.map((pl) => <li key={pl.name}><b>{pl.name}</b> <span className="quiet">({pl.kind}{pl.stakeholder ? `, stakeholder ${pl.stakeholder}` : ""})</span>{pl.goals ? `: ${pl.goals}` : ""}</li>)}</ul>
          {(r.games || []).map((g) => <Game key={g.name} g={g} w={(res.games || []).find((x) => x.name === g.name)} />)}
        </section>)}
    </div>
  );
}

export default function ScenarioPlanningTab({ p }) {
  const { data, error } = useApi(`/api/v1/projects/${p.id}/scenario-planning`);
  const [ver, setVer] = useState(null);
  const { data: old } = useApi(ver ? `/api/v1/projects/${p.id}/scenario-planning/${ver}` : null);
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet"><span className="spinner" aria-hidden="true" /> Loading the scenario planning…</p>;
  const shown = ver && old ? old : data.latest;
  return (
    <div className="scenario-planning-tab">
      <p className="quiet small">Read only. The study is made with your AI assistant through MCP: ask it to <i>run the scenario planning wizard for {p.name}</i>
        (the prompt <code>scenario_planning_wizard</code>). Each run is kept as a dated version.</p>
      {data.signposts_due > 0 && <p className="status warn">{data.signposts_due} signpost(s) due at this review.</p>}
      {data.versions.length > 1 && (
        <p className="small"><label>Version{" "}
          <select value={ver || ""} onChange={(e) => setVer(e.target.value || null)}>
            <option value="">The newest finished</option>
            {data.versions.map((v) => <option key={v.version} value={v.version}>{`${v.version}: ${v.status === "draft" ? "draft" : fmtDateTime(v.finished_at)} · ${v.question}`}</option>)}
          </select></label></p>)}
      {shown ? <Study r={shown} signposts={ver ? null : data.signposts} /> : <p className="quiet">No study is finished yet.</p>}
      {data.draft && !ver && <p className="quiet small">A draft, version {data.draft.version}, is being worked on: {data.draft.question}</p>}
    </div>
  );
}
