// Customer journey maps (R5.7-J1, D730): a tab of the project beside the Business Model Canvas, standing on its own
// like the canvas. A journey is a grid to work in: its stages across; under each stage its steps (each with the
// emotion there, -2 to +2, drawn as a curve above them with zero as the line), touchpoints, pain points, moments that
// matter, opportunities and the project's own kinds of part; the personas above; the model elements each stage links
// to below. A cell is edited by clicking it. Versions like the canvas: current, target, working copy, scenario; draft
// or agreed; two journeys compared stage by stage; PDF, PowerPoint and draw.io (the drawn view for presentations).
import { useState } from "react";
import { apiBlobUrl, apiDownload, apiFetch, apiUpload } from "./auth";
import { openInDrawio } from "./drawioScratch";
import { refreshAll, useApi } from "./ModelViews";
import { liveProjects } from "./ModelMarks";

const KINDS = { current: "Current state", target: "Target state", working: "Working copy", scenario: "Scenario" };
const STATUSES = { draft: "Draft", agreed: "Agreed" };
const FACES = { "-2": ["😣", "Very unhappy"], "-1": ["🙁", "Unhappy"], 0: ["😐", "Neutral"], 1: ["🙂", "Happy"], 2: ["😄", "Very happy"] };
const when = (v) => (v ? new Date(v).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "");
const face = (s) => (s === null || s === undefined ? null : FACES[String(s)]);

// the emotion at a step: five faces to pick from (or none)
function Faces({ value, onChange }) {
  return (
    <span className="jm-faces" role="radiogroup" aria-label="Emotion">
      {[-2, -1, 0, 1, 2].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} title={`${FACES[String(n)][1]} (${n > 0 ? "+" : ""}${n})`}
          className={`jm-face${value === n ? " on" : ""}`} onClick={() => onChange(value === n ? null : n)}>{FACES[String(n)][0]}</button>))}
    </span>
  );
}

function PartEditor({ part, kind, item, onSave, onCancel, onRemove, busy }) {
  const [t, setT] = useState(item?.text || "");
  const [n, setN] = useState(item?.note || "");
  const [sc, setSc] = useState(item?.score ?? null);
  const [f, setF] = useState(item?.fields || {});
  const save = () => onSave({ text: t, note: n, ...(part === "step" ? { score: sc === null ? "" : sc } : {}), ...(kind?.fields?.length ? { fields: f } : {}) });
  return (
    <div className="jm-edit">
      <input autoFocus value={t} onChange={(e) => setT(e.target.value)} placeholder={kind?.help || "Write it"} aria-label="Text"
        onKeyDown={(e) => { if (e.key === "Enter" && t.trim()) save(); if (e.key === "Escape") onCancel(); }} />
      {part === "step" && <Faces value={sc} onChange={setSc} />}
      {(kind?.fields || []).map((k) => <input key={k} value={f[k] || ""} placeholder={k} aria-label={k} onChange={(e) => setF({ ...f, [k]: e.target.value })} />)}
      <input value={n} onChange={(e) => setN(e.target.value)} placeholder="A note (optional)" aria-label="Note" />
      <div className="row-gap small">
        <button className="primary small" disabled={!t.trim() || busy} onClick={save}>Save</button>
        {onRemove && <button className="small" onClick={onRemove}>Remove</button>}
        <button className="linkish" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function Card({ it, part, state, onClick }) {
  const fc = part === "step" ? face(it.score) : null;
  const was = it.was_score !== null && it.was_score !== undefined ? face(it.was_score) : null;
  return (
    <div className={`jm-card ${state && state !== "same" ? state : ""}${onClick ? " click" : ""}`} title={it.note || ""}
      onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === "Enter") onClick(); } : undefined}>
      {it.was_text && <div className="jm-was">{it.was_text}</div>}
      <div className="jm-text">{fc && <span className="jm-fc" title={fc[1]}>{was && <s>{was[0]}</s>}{fc[0]}</span>}{it.text}</div>
      {Object.entries(it.fields || {}).map(([k, v]) => <div key={k} className="jm-field small"><b>{k}:</b> {v}</div>)}
      {it.note && <div className="jm-note">{it.note}</div>}
    </div>
  );
}

// the emotion curve: a point per step across the stages, +2 at the top, zero the line
function Curve({ stages }) {
  const W = 1000, H = 120, n = Math.max(1, stages.length), cw = W / n;
  const pts = [];
  stages.forEach((s, i) => {
    const steps = (s.parts?.step || []).filter((r) => r.state !== "removed");
    steps.forEach((r, k) => {
      if (r.score === null || r.score === undefined) return;
      pts.push({ x: i * cw + ((k + 1) * cw) / (steps.length + 1), y: H / 2 - (r.score * (H / 2 - 16)) / 2, r });
    });
  });
  // the lines stretch with the grid; the faces sit over them as text, so they keep their shape
  return (
    <div className="jm-curve-box" role="img" aria-label={`Emotion across the journey: ${pts.map((p) => p.r.score).join(", ") || "none scored yet"}`}>
      <svg className="jm-curve" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="jm-zero" />
        {stages.map((_s, i) => i > 0 && <line key={i} x1={i * cw} x2={i * cw} y1="0" y2={H} className="jm-sep" />)}
        {pts.length > 1 && <polyline points={pts.map((p) => `${p.x},${p.y}`).join(" ")} className="jm-line" />}
      </svg>
      {pts.map((p, i) => <span key={i} className={`jm-pt s${p.r.score}`} style={{ left: `${(p.x / W) * 100}%`, top: `${(p.y / H) * 100}%` }}
        title={`${p.r.text}: ${FACES[String(p.r.score)][1]}`}>{FACES[String(p.r.score)][0]}</span>)}
    </div>
  );
}

function LinkPicker({ url, onPick, onCancel }) {
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const { data } = useApi(`${url}/journeys/elements?q=${encodeURIComponent(q)}${all ? "&type=all" : ""}`);
  return (
    <div className="jm-pick">
      <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find an element of the project's models" aria-label="Find an element" />
      <label className="small"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> any type</label>
      <ul className="small">
        {(data?.elements || []).slice(0, 12).map((e) => <li key={e.entity}><button className="linkish" onClick={() => onPick(e.entity)}>{e.entity_type}: {e.name}</button>
          <span className="quiet"> · {e.model_name}</span></li>)}
        {data && !data.elements?.length && <li className="quiet">{data.message || "Nothing found."}</li>}
      </ul>
      <button className="linkish small" onClick={onCancel}>Close</button>
    </div>
  );
}

function Grid({ j, parts, may, url, act, editing, setEditing, busy, compare }) {
  const stages = j.stages || [];
  const shown = parts.filter((k) => k.code === "step" || stages.some((s) => (s.parts?.[k.code] || []).length) || may);
  const [picking, setPicking] = useState("");
  return (
    <div className="jm-scroll">
      <table className="jm-grid" style={{ minWidth: 160 + stages.length * 220 }}>
        <thead><tr><th className="jm-lab" />
          {stages.map((s, i) => (
            <th key={s.id || i} className={`jm-stage ${s.state && s.state !== "same" ? s.state : ""}`}>
              {editing === `stage:${s.id}` ? <StageEditor s={s} busy={busy} onCancel={() => setEditing(null)}
                onSave={(b) => act(() => apiFetch(`${url}/journey-stages/${s.id}`, { method: "PUT", body: JSON.stringify(b) }))}
                onRemove={() => { if (window.confirm(`Remove the stage ${s.name} and everything under it?`)) act(() => apiFetch(`${url}/journey-stages/${s.id}`, { method: "DELETE" })); }}
                onMove={(d) => { const ids = stages.map((x) => x.id); const k = ids.indexOf(s.id); const t = k + d; if (t < 0 || t >= ids.length) return;
                  [ids[k], ids[t]] = [ids[t], ids[k]]; act(() => apiFetch(`${url}/journeys/${j.id}/reorder`, { method: "POST", body: JSON.stringify({ stages: ids }) })); }} />
                : <div className={may ? "click" : ""} onClick={may ? () => setEditing(`stage:${s.id}`) : undefined} title={s.note || ""}>
                  {s.was_name && <s className="jm-was">{s.was_name}</s>}<b>{s.name}</b>{s.note && <div className="small jm-stage-note">{s.note}</div>}</div>}
            </th>))}
          {may && <th className="jm-addstage">{editing === "stage:new"
            ? <StageEditor s={{ name: "", note: "" }} busy={busy} onCancel={() => setEditing(null)}
              onSave={(b) => act(() => apiFetch(`${url}/journeys/${j.id}/stages`, { method: "POST", body: JSON.stringify(b) }))} />
            : <button className="linkish" onClick={() => setEditing("stage:new")}>＋ stage</button>}</th>}
        </tr></thead>
        <tbody>
          <tr className="jm-emotion"><th className="jm-lab">Emotion<div className="small quiet">from the steps</div></th>
            <td colSpan={Math.max(1, stages.length)}><Curve stages={stages} /></td>{may && <td />}</tr>
          {shown.map((k) => (
            <tr key={k.code}>
              <th className="jm-lab" title={k.help}>{k.label}{!k.standard && <div className="small quiet">our own</div>}</th>
              {stages.map((s, i) => (
                <td key={s.id || i}>
                  {(s.parts?.[k.code] || []).map((it, n) => (editing === it.id
                    ? <PartEditor key={it.id} part={k.code} kind={k} item={it} busy={busy} onCancel={() => setEditing(null)}
                      onSave={(b) => act(() => apiFetch(`${url}/journey-items/${it.id}`, { method: "PUT", body: JSON.stringify(b) }))}
                      onRemove={() => act(() => apiFetch(`${url}/journey-items/${it.id}`, { method: "DELETE" }))} />
                    : <Card key={it.id || n} it={it} part={k.code} state={compare ? it.state : ""} onClick={may && !compare ? () => setEditing(it.id) : undefined} />))}
                  {may && !compare && (editing === `new:${s.id}:${k.code}`
                    ? <PartEditor part={k.code} kind={k} busy={busy} onCancel={() => setEditing(null)}
                      onSave={(b) => act(() => apiFetch(`${url}/journeys/${j.id}/items`, { method: "POST", body: JSON.stringify({ ...b, stage: s.id, part: k.code }) }))} />
                    : <button className="linkish small jm-add" onClick={() => setEditing(`new:${s.id}:${k.code}`)} aria-label={`Add to ${k.label} in ${s.name}`}>＋</button>)}
                </td>))}
              {may && <td />}
            </tr>))}
          <tr className="jm-links"><th className="jm-lab">Linked elements<div className="small quiet">in the project's models</div></th>
            {stages.map((s, i) => (
              <td key={s.id || i}>
                {(s.links || []).map((x) => <div key={x.id || x.entity} className={`jm-link small ${x.state && x.state !== "same" ? x.state : ""}`}>
                  <span className="quiet">{x.entity_type}:</span> {x.name}
                  {may && !compare && <button className="linkish" aria-label={`Take off ${x.name}`} onClick={() => act(() => apiFetch(`${url}/journey-links/${x.id}`, { method: "DELETE" }))}> ×</button>}</div>)}
                {may && !compare && (picking === s.id
                  ? <LinkPicker url={url} onCancel={() => setPicking("")}
                    onPick={(entity) => act(() => apiFetch(`${url}/journeys/${j.id}/links`, { method: "POST", body: JSON.stringify({ stage: s.id, entity }) })).then(() => setPicking(""))} />
                  : <button className="linkish small jm-add" onClick={() => setPicking(s.id)}>＋ link</button>)}
              </td>))}
            {may && <td />}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function StageEditor({ s, onSave, onCancel, onRemove, onMove, busy }) {
  const [name, setName] = useState(s.name);
  const [note, setNote] = useState(s.note || "");
  return (
    <div className="jm-edit">
      <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Stage, e.g. Report the claim" aria-label="Stage name"
        onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) onSave({ name, note }); if (e.key === "Escape") onCancel(); }} />
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What happens here (optional)" aria-label="Stage note" />
      <div className="row-gap small">
        <button className="primary small" disabled={!name.trim() || busy} onClick={() => onSave({ name, note })}>Save</button>
        {onMove && <><button className="small" onClick={() => onMove(-1)} title="Move left">◀</button><button className="small" onClick={() => onMove(1)} title="Move right">▶</button></>}
        {onRemove && <button className="small" onClick={onRemove}>Remove</button>}
        <button className="linkish" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function Personas({ j, may, url, act, busy, compare }) {
  const [adding, setAdding] = useState(false);
  const [t, setT] = useState("");
  return (
    <div className="jm-personas small">
      <b>Personas</b>{" "}
      {(j.personas || []).map((p, i) => <span key={p.id || i} className={`chip jm-persona ${compare && p.state !== "same" ? p.state : ""}`}>{p.text}
        {may && !compare && <button className="linkish" aria-label={`Remove ${p.text}`} onClick={() => act(() => apiFetch(`${url}/journey-items/${p.id}`, { method: "DELETE" }))}> ×</button>}</span>)}
      {!(j.personas || []).length && <span className="quiet">none yet</span>}
      {may && !compare && (adding
        ? <span className="row-gap"><input autoFocus value={t} onChange={(e) => setT(e.target.value)} placeholder="Who, in a few words" aria-label="Persona" />
          <button className="small primary" disabled={!t.trim() || busy} onClick={() => act(() => apiFetch(`${url}/journeys/${j.id}/items`,
            { method: "POST", body: JSON.stringify({ part: "persona", text: t }) })).then((ok) => { if (ok) { setT(""); setAdding(false); } })}>Add</button>
          <button className="linkish" onClick={() => setAdding(false)}>Cancel</button></span>
        : <button className="linkish" onClick={() => setAdding(true)}> ＋ persona</button>)}
    </div>
  );
}

function PartKinds({ parts, url, act, busy }) {
  const [f, setF] = useState({ label: "", fields: "", code: "" });
  return (
    <details className="jm-kinds small">
      <summary>Kinds of part and their fields</summary>
      <ul>{parts.map((k) => <li key={k.code}><b>{k.label}</b>{k.standard ? "" : " (ours)"}{k.fields.length ? `: ${k.fields.join(", ")}` : ""}
        {(!k.standard || k.fields.length > 0) && <button className="linkish" onClick={() => act(() => apiFetch(`${url}/journey-kinds/${k.code}`, { method: "DELETE" }))}>
          {k.standard ? " take off its fields" : " remove"}</button>}</li>)}</ul>
      <div className="row-gap">
        <select value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} aria-label="Which kind">
          <option value="">A new kind of part…</option>
          {parts.filter((k) => k.standard).map((k) => <option key={k.code} value={k.code}>Fields on {k.label}</option>)}
        </select>
        {!f.code && <input value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} placeholder="Its name, e.g. Systems behind it" aria-label="Kind name" />}
        <input value={f.fields} onChange={(e) => setF({ ...f, fields: e.target.value })} placeholder="Fields, separated by commas" aria-label="Fields" />
        <button disabled={busy || (!f.code && !f.label.trim())} onClick={() => act(() => apiFetch(`${url}/journey-kinds`, { method: "POST",
          body: JSON.stringify({ code: f.code || undefined, label: f.label, fields: f.fields.split(",").map((x) => x.trim()).filter(Boolean) }) }))
          .then((ok) => ok && setF({ label: "", fields: "", code: "" }))}>Save</button>
      </div>
    </details>
  );
}

function Documents({ p, j, may, act, url, setMsg }) {
  const [file, setFile] = useState(null);
  const [note, setNote] = useState("");
  const [pick, setPick] = useState("");
  const have = new Set(j.documents.map((d) => d.id));
  const others = (p.documents || []).filter((d) => (d.file_name || d.title) && !have.has(d.id));
  const base = `${url}/journeys/${j.id}`;
  return (
    <div className="bmc-docs">
      <h4>Documents behind this journey</h4>
      {!j.documents.length && <p className="quiet small">None yet: add what it was built from (interviews, surveys, research).</p>}
      <ul className="small">{j.documents.map((d) => (
        <li key={d.id}><button className="linkish" onClick={() => apiDownload(`${url}/documents/${d.id}`, d.file_name).catch((e) => setMsg(e.message))}>📄 {d.title || d.file_name}</button>
          {d.note && <span className="quiet"> · {d.note}</span>}<span className="quiet"> · {d.added_by}, {when(d.added_at)}</span>
          {may && <> · <button className="linkish" onClick={() => act(() => apiFetch(`${base}/documents/${d.id}`, { method: "DELETE" }))}>take off</button></>}</li>))}</ul>
      {may && (
        <div className="row-gap small bmc-docs-add">
          <input type="file" onChange={(e) => setFile(e.target.files[0] || null)} aria-label="Upload a document" />
          <span className="quiet">or</span>
          <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="A document of the project">
            <option value="">a document of the project…</option>
            {others.map((d) => <option key={d.id} value={d.id}>{d.title || d.file_name}</option>)}
          </select>
          <input placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Document note" />
          <button disabled={!file && !pick} onClick={() => act(() => {
            if (file) { const fd = new FormData(); fd.append("file", file); fd.append("note", note); return apiUpload(`${base}/documents`, fd); }
            return apiFetch(`${base}/documents`, { method: "POST", body: JSON.stringify({ document: pick, note }) });
          }).then((ok) => { if (ok) { setFile(null); setPick(""); setNote(""); } })}>Add</button>
        </div>
      )}
    </div>
  );
}

function NewJourney({ url, act, busy, onMade, onCancel, templates }) {
  const [f, setF] = useState({ name: "", kind: "current", template: "starter", persona: "", description: "" });
  return (
    <div className="goal-box">
      <div className="own-row">
        <input placeholder="Name, e.g. Make a motor claim" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Journey name" />
        <select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} aria-label="Kind">
          {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select value={f.template} onChange={(e) => setF({ ...f, template: e.target.value })} aria-label="Start from">
          {Object.entries(templates || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
      <input className="wide" placeholder="Whose journey, e.g. a motor policyholder (optional)" value={f.persona} onChange={(e) => setF({ ...f, persona: e.target.value })} aria-label="Whose journey" />
      <input className="wide" placeholder="What it is for (optional)" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} aria-label="Description" />
      <div className="row-gap">
        <button className="primary" disabled={!f.name.trim() || busy}
          onClick={() => act(() => apiFetch(`${url}/journeys`, { method: "POST", body: JSON.stringify(f) })).then((r) => r && onMade(r.id))}>Make the journey</button>
        <button className="linkish" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

export function JourneysTab({ p }) {
  const url = `/api/v1/projects/${p.id}`;
  const { data: list } = useApi(`${url}/journeys`);
  const { data: plist_ } = useApi("/api/v1/projects");
  const plist = plist_ && { ...plist_, projects: liveProjects(plist_.projects) };   // never a frozen project (D360)
  const params = new URLSearchParams((window.location.hash.split("?")[1]) || "");
  const [sel, setSel] = useState(params.get("j") || "");
  const [cmpWith, setCmpWith] = useState("");
  const [making, setMaking] = useState(false);
  const [editing, setEditing] = useState(null);
  const [dialog, setDialog] = useState("");           // rename | copy | copy-to
  const [form, setForm] = useState({});
  const [hist, setHist] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const journeys = list?.journeys || [];
  const current = sel || journeys[0]?.id || "";
  const { data: j } = useApi(current ? `${url}/journeys/${current}` : null);
  const { data: cmp } = useApi(current && cmpWith ? `${url}/journeys/${current}/compare/${cmpWith}` : null);
  const may = p.may_contribute && !p.frozen;
  const parts = list?.parts || [];
  async function act(fn) {
    setBusy(true); setMsg("");
    try { const r = await fn(); setMsg(r?.message || ""); setEditing(null); refreshAll(); return r || true; }
    catch (e) { setMsg(e.message); return false; } finally { setBusy(false); }
  }
  const choose = (id) => { setSel(id); setCmpWith(""); setDialog(""); setEditing(null); setHist(false); };
  const made = (id) => { setMaking(false); setDialog(""); setCmpWith(""); if (id) setSel(id); };
  const exp = (fmt, other) => {
    const q = `${url}/journeys/${current}/export?format=${fmt}${other ? `&compare=${other}` : ""}`;
    const title = other && cmp ? `${cmp.a.name} to ${cmp.b.name}` : j?.name || "journey";
    if (fmt === "drawio") {                // our own draw.io in a tab of its own, kept nowhere (D585)
      apiBlobUrl(q).then(async (u) => { const xml = await (await fetch(u)).text(); URL.revokeObjectURL(u); openInDrawio({ model: null, title, xml }); })
        .catch((e) => setMsg(e.message));
      return;
    }
    apiDownload(q, `${title}.${fmt}`).catch((e) => setMsg(e.message));
  };
  const cmpParts = cmp ? parts.filter((k) => cmp.parts.includes(k.code)) : parts;
  return (
    <div className="bmc-tab jm-tab">
      <p className="quiet small">Customer journey maps for this project: how a person moves through their journey with us, stage by stage,
        and how they feel at each step. They stand on their own like the canvas: links to the models' elements point out to them and
        change nothing there. Make the current state, copy it to a target state, and compare the two.</p>
      <div className="bmc-list">
        {journeys.map((x) => (
          <button key={x.id} className={`bmc-card${x.id === current ? " on" : ""}`} onClick={() => choose(x.id)}>
            <b>{x.name}</b>
            <span className="small"><span className={`kind ${x.kind}`}>{KINDS[x.kind]}</span> · {STATUSES[x.status]} · {x.stages} stages · {x.steps} steps
              {x.emotion !== null && x.emotion !== undefined ? ` · ${face(Math.round(x.emotion))?.[0] || ""} ${x.emotion > 0 ? "+" : ""}${x.emotion}` : ""}</span>
            {x.source_name && <span className="small quiet">from {x.source_name}</span>}
          </button>))}
        {may && !making && <button className="bmc-card new" onClick={() => setMaking(true)}>＋ New journey</button>}
      </div>
      {making && <NewJourney url={url} act={act} busy={busy} templates={list?.templates} onMade={made} onCancel={() => setMaking(false)} />}
      {!journeys.length && !making && <p className="quiet">No journey yet.{may ? " Make the first: the starter gives you typical stages to change." : ""}</p>}

      {j && !cmpWith && <>
        <div className="bmc-head">
          <div>
            <h3>{j.name} <span className={`kind ${j.kind}`}>{KINDS[j.kind]}</span> <span className={`chip ${j.status}`}>{STATUSES[j.status]}</span></h3>
            <div className="small quiet">{j.persona && <>for {j.persona} · </>}{j.description && <>{j.description} · </>}
              {j.source && <>made from <button className="linkish" onClick={() => choose(j.source.id)}>{j.source.name}</button> · </>}
              {!j.source && j.source_note && <>{j.source_note} · </>}{j.changed_by || j.created_by}, {when(j.changed_at || j.created_at)}</div>
          </div>
          <div className="row-gap small bmc-actions">
            {may && <button onClick={() => { setDialog("copy"); setForm({ name: `${j.name.replace(/ \((today|current state)\)$/i, "")} (target)`, kind: "target" }); }}>Make a copy…</button>}
            <select value="" onChange={(e) => e.target.value && setCmpWith(e.target.value)} aria-label="Compare with">
              <option value="">Compare with…</option>
              {journeys.filter((x) => x.id !== j.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
            <select value="" onChange={(e) => e.target.value && exp(e.target.value)} aria-label="Export">
              <option value="">Export…</option><option value="pdf">PDF</option><option value="pptx">PowerPoint</option><option value="drawio">Open in draw.io</option>
            </select>
            {may && <select value="" onChange={(e) => { const v = e.target.value; if (!v) return;
              if (v === "rename") { setDialog("rename"); setForm({ name: j.name, description: j.description, persona: j.persona }); }
              else if (v === "copy-to") { setDialog("copy-to"); setForm({ project: "" }); }
              else if (v === "delete") { if (window.confirm(`Remove the journey ${j.name}?`)) act(() => apiFetch(`${url}/journeys/${j.id}`, { method: "DELETE" })).then((r) => r && setSel("")); }
              else if (v.startsWith("kind:")) act(() => apiFetch(`${url}/journeys/${j.id}`, { method: "PUT", body: JSON.stringify({ kind: v.slice(5) }) }));
              else if (v.startsWith("status:")) act(() => apiFetch(`${url}/journeys/${j.id}`, { method: "PUT", body: JSON.stringify({ status: v.slice(7) }) }));
            }} aria-label="More">
              <option value="">More…</option>
              {j.status === "draft" ? <option value="status:agreed">Mark it agreed</option> : <option value="status:draft">Make it a draft again</option>}
              {Object.entries(KINDS).filter(([k]) => k !== j.kind).map(([k, v]) => <option key={k} value={`kind:${k}`}>Make it a {v.toLowerCase()}</option>)}
              <option value="rename">Rename or describe…</option>
              <option value="copy-to">Copy to another project…</option>
              <option value="delete">Remove this journey</option>
            </select>}
            <button className="linkish" onClick={() => setHist(!hist)}>History ({j.history.length})</button>
          </div>
        </div>
        {dialog && (
          <div className="goal-box bmc-dialog">
            {dialog !== "copy-to" && <input className="wide" value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Name" />}
            {dialog === "rename" && <>
              <input className="wide" value={form.persona || ""} placeholder="Whose journey" onChange={(e) => setForm({ ...form, persona: e.target.value })} aria-label="Whose journey" />
              <input className="wide" value={form.description || ""} placeholder="What it is for" onChange={(e) => setForm({ ...form, description: e.target.value })} aria-label="Description" /></>}
            {dialog === "copy" && <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} aria-label="Kind of the copy">
              {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}
            {dialog === "copy-to" && <select value={form.project} onChange={(e) => setForm({ ...form, project: e.target.value })} aria-label="To project">
              <option value="">the project to copy it to…</option>
              {(plist?.projects || []).filter((x) => x.id !== p.id && !x.base_kind).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>}
            <div className="row-gap">
              <button className="primary" disabled={busy || (dialog === "copy-to" ? !form.project : !(form.name || "").trim())} onClick={() => {
                const call = dialog === "rename" ? apiFetch(`${url}/journeys/${j.id}`, { method: "PUT", body: JSON.stringify(form) })
                  : apiFetch(`${url}/journeys/${j.id}/${dialog}`, { method: "POST", body: JSON.stringify(form) });
                act(() => call).then((r) => r && made(dialog === "copy" ? r.id : null));
              }}>{{ copy: "Make the copy", rename: "Save", "copy-to": "Copy it" }[dialog]}</button>
              <button className="linkish" onClick={() => setDialog("")}>Cancel</button>
            </div>
          </div>
        )}
        <Personas j={j} may={may} url={url} act={act} busy={busy} />
        {!j.stages.length && <p className="quiet small">No stages yet{may ? ": add the first with ＋ stage." : "."}</p>}
        <Grid j={j} parts={parts} may={may} url={url} act={act} editing={editing} setEditing={setEditing} busy={busy} />
        {may && <PartKinds parts={parts} url={url} act={act} busy={busy} />}
        {hist && <ul className="small kq-history">{j.history.map((h, i) => <li key={i}><span className="quiet">{when(h.at)}</span> {h.username} {h.action}{h.note ? `: ${h.note}` : ""}</li>)}</ul>}
        <Documents p={p} j={j} may={may} act={act} url={url} setMsg={setMsg} />
      </>}

      {cmpWith && cmp && <>
        <div className="bmc-head">
          <div>
            <h3>{cmp.a.name} → {cmp.b.name}</h3>
            <div className="small"><span className="bmc-key added">{cmp.counts.added} added</span> <span className="bmc-key changed">{cmp.counts.changed} changed</span>{" "}
              <span className="bmc-key removed">{cmp.counts.removed} removed</span> <span className="quiet">{cmp.counts.same} the same</span></div>
          </div>
          <div className="row-gap small bmc-actions">
            <button onClick={() => { const a = cmp.a.id; setSel(cmp.b.id); setCmpWith(a); }}>Swap</button>
            <select value="" onChange={(e) => e.target.value && exp(e.target.value, cmpWith)} aria-label="Export the comparison">
              <option value="">Export…</option><option value="pdf">PDF</option><option value="pptx">PowerPoint</option><option value="drawio">Open in draw.io</option>
            </select>
            <button className="linkish" onClick={() => setCmpWith("")}>Close the comparison</button>
          </div>
        </div>
        <Personas j={cmp} compare />
        <Grid j={cmp} parts={cmpParts} may={false} url={url} act={act} editing={null} setEditing={() => {}} busy={false} compare />
      </>}
      {msg && <p className="small status">{msg}</p>}
    </div>
  );
}
