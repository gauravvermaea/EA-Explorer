// Enterprise discovery (R5.5; the owner's design, 15 Nov 2026, 20:11 to 20:28): EA Explorer keeps the discovery
// projects (a target model, the sources, the defaults of a run and a schedule that marks when a run is due) and takes
// back what the people's own AI found through MCP. #/discovery-projects lists them; #/discovery-projects/<id> shows
// one with its sources (Test the link: the sign-in is used once, then forgotten) and its runs, each with its report.
// An element's "Found in" tab (ModelViews) shows where runs found it.
import { useState } from "react";
import { apiFetch } from "./auth";
import { liveModels } from "./ModelMarks";
import { Field, Modal, NewModelDialog } from "./ModelOps";
import { can } from "./auth";
import { refreshAll, useApi } from "./ModelViews";
import { fmtDateTime } from "./fmt";

const URL = "/api/v1/discovery-projects";
const DUE = { due: ["Due", ""], overdue: ["Overdue", " bad"], running: ["Running", " ok"] };
// the models a discovery project may commit into: live working models (the same rule as the server)
export const targetModels = (list) => liveModels(list).filter((m) => m.kind === "project" && !m.is_locked && (m.lock_level || "none") === "none");
const safeLink = (l) => (/^https?:\/\//i.test(l || "") ? l : "");
const dueChip = (d) => (d && DUE[d] ? <span className={`chip small${DUE[d][1]}`}>{DUE[d][0]}</span> : null);

export default function DiscoveryProjects({ route }) {
  const id = decodeURIComponent((route.split("?")[0].split("/")[2] || ""));
  return id ? <ProjectPage id={id} /> : <ProjectList />;
}

function HowToRun({ name }) {
  return (
    <div className="disc-how">
      <strong>How it runs.</strong> EA Explorer keeps the setup and takes back what is found; your own AI assistant,
      connected through MCP (AI (MCP) › Connect your AI assistant), reaches each source with its own access and does the
      reading. Ask it: <code>run discovery project {name || "<name>"}</code>. For the schedule, give your AI client a
      scheduled task that asks <code>discovery projects due</code> and runs each. Anything marked NOT FOR AI USE OR
      AUTOMATED PROCESSING is never read: the AI lists its title as skipped.
    </div>
  );
}

function ProjectList() {
  const { data, error } = useApi(URL);
  const [dlg, setDlg] = useState(null);
  const [msg, setMsg] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet">Loading...</p>;
  return (
    <section>
      <h1>Enterprise discovery</h1>
      <p className="quiet">Discovery projects: each names a target model and the sources it covers. Your AI reads the
        sources, builds the metamodel and content in the target model, and says where each element was found. Every run
        tags the model before and after, so you can compare what it changed.</p>
      <HowToRun />
      {msg && <p className="status ok">{msg}</p>}
      {data.may_edit
        ? <p><button className="primary" onClick={() => setDlg({})}>＋ Set up a discovery project</button></p>
        : <p className="small quiet">Discovery Admins (and Super Admins) set up discovery projects.</p>}
      {!data.projects.length ? <p className="quiet">No discovery project yet.</p> : (
        <table className="grid-table">
          <thead><tr><th>Name</th><th>Target model</th><th>Sources</th><th>Schedule</th><th>Next run due</th><th>Last run</th></tr></thead>
          <tbody>{data.projects.map((p) => (
            <tr key={p.id} className={p.due === "overdue" ? "stuck" : ""}>
              <td><a href={`#/discovery-projects/${p.id}`}>{p.name}</a></td>
              <td><a href={`#/metamodel/${p.target_model.id}`}>{p.target_model.name}</a></td>
              <td>{p.resources}</td><td className="small">{p.schedule_text}</td>
              <td className="small nowrap">{p.next_due_at ? fmtDateTime(p.next_due_at) : "–"} {dueChip(p.due)}</td>
              <td className="small">{p.last_run ? `Run ${p.last_run.number}: ${p.last_run.status}` : "Not run yet"}</td>
            </tr>))}</tbody>
        </table>)}
      {dlg && <ProjectDialog p={dlg} data={data} onClose={(m) => { setDlg(null); if (m) { setMsg(m); refreshAll(); } }} />}
    </section>
  );
}

function ProjectDialog({ p, data, onClose }) {
  const { data: models } = useApi("/api/v1/models");
  const [f, setF] = useState({ name: p.name || "", purpose: p.purpose || "", target_model: p.target_model?.id || "",
    read_default: p.read_default || "new", gone_default: p.gone_default || "mark", schedule: p.schedule || "none",
    schedule_day: p.schedule_day || 1, schedule_time: p.schedule_time || "02:00" });
  const [err, setErr] = useState("");
  const [newModel, setNewModel] = useState(false);
  const [made, setMade] = useState(null);           // a model made here, shown before the list has it
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  // working models only: no library models or root metamodels, nothing frozen, archived, read-only or locked (R5.5)
  const list = targetModels(Array.isArray(models) ? models : models?.models || []);
  const shown = made && !list.some((m) => m.id === made.id) ? [made, ...list] : list;
  async function save() {
    try { const out = await apiFetch(p.id ? `${URL}/${p.id}` : URL, { method: p.id ? "PUT" : "POST", body: JSON.stringify(f) }); onClose(out.message || "Saved."); }
    catch (e) { setErr(e.message); }
  }
  return (
    <Modal title={p.id ? `Discovery project ${p.name}` : "Set up a discovery project"} onClose={() => onClose()}
      actions={<><button onClick={() => onClose()}>Cancel</button><button className="primary" onClick={save}>Save</button></>}>
      {err && <p className="status bad">{err}</p>}
      <Field label="Name"><input value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
      <Field label="Purpose"><textarea rows={2} value={f.purpose} onChange={(e) => set("purpose", e.target.value)} /></Field>
      <Field label="Target model" tip="The model the AI commits into: a child of the main model to review first (merged with the usual merge), or the main model once you trust the AI.">
        <div className="row-gap">
          <select value={f.target_model} onChange={(e) => set("target_model", e.target.value)}>
            <option value="">Choose a model</option>{shown.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
          <button type="button" onClick={() => setNewModel(true)} disabled={!can("models.create") && !can("library.curate")}
            title="A new working model, picked here as the target (a child of the main model to review the AI's work first)">＋ New model</button>
        </div></Field>
      {newModel && <NewModelDialog preset={{ link: "child" }} onClose={() => setNewModel(false)}
        onCreated={(m) => { setMade(m); set("target_model", m.id); }} />}
      <div className="row-gap">
        <Field label="A run reads" tip="The AI is asked each time; this is the default it suggests, and what a scheduled run uses.">
          <select value={f.read_default} onChange={(e) => set("read_default", e.target.value)}>
            {Object.entries(data.read_modes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="What is gone from a source" tip="An element whose source item is no longer there. The AI is asked each time; the run's tags still allow compare and undo.">
          <select value={f.gone_default} onChange={(e) => set("gone_default", e.target.value)}>
            {Object.entries(data.gone_modes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
      </div>
      <div className="row-gap">
        <Field label="Schedule" tip="Marks when a run is due; EA Explorer runs nothing. Your AI client's scheduled task asks which projects are due. A run more than two hours late shows as overdue (and in the alerts).">
          <select value={f.schedule} onChange={(e) => set("schedule", e.target.value)}>
            <option value="none">No schedule</option><option value="daily">Every day</option>
            <option value="weekly">Every week</option><option value="monthly">Every month</option></select></Field>
        {f.schedule === "weekly" && <Field label="On"><select value={f.schedule_day} onChange={(e) => set("schedule_day", Number(e.target.value))}>
          {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((d, i) => <option key={d} value={i + 1}>{d}</option>)}</select></Field>}
        {f.schedule === "monthly" && <Field label="Day of the month"><input type="number" min={1} max={28} value={f.schedule_day} onChange={(e) => set("schedule_day", Number(e.target.value))} /></Field>}
        {f.schedule !== "none" && <Field label="At (UTC)"><input type="time" value={f.schedule_time} onChange={(e) => set("schedule_time", e.target.value)} /></Field>}
      </div>
    </Modal>
  );
}

function ProjectPage({ id }) {
  const url = `${URL}/${encodeURIComponent(id)}`;
  const { data, error } = useApi(url);
  const { data: meta } = useApi(URL);
  const [dlg, setDlg] = useState(null);
  const [src, setSrc] = useState(null);
  const [run, setRun] = useState(null);
  const [msg, setMsg] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!data || !meta) return <p className="quiet">Loading...</p>;
  const done = (m) => { setDlg(null); setSrc(null); if (m) { setMsg(m); refreshAll(); } };
  async function remove() {
    if (!window.confirm(`Delete discovery project ${data.name}? Its sources and runs go; what the runs added stays in the model.`)) return;
    try { await apiFetch(url, { method: "DELETE" }); window.location.hash = "#/discovery-projects"; refreshAll(); }
    catch (e) { setMsg(e.message); }
  }
  return (
    <section>
      <p className="quiet crumbs"><a href="#/discovery-projects">Enterprise discovery</a> / {data.name}</p>
      <h1>{data.name} {dueChip(data.due)}</h1>
      {data.purpose && <p>{data.purpose}</p>}
      <p className="small">Target model <a href={`#/metamodel/${data.target_model.id}`}>{data.target_model.name}</a> · set up by {data.set_up_by} (runs are
        made by the "AI agent on behalf of {data.set_up_by}") · {data.schedule_text}
        {data.next_due_at ? ` · next run due ${fmtDateTime(data.next_due_at)}` : ""} · a run reads {meta.read_modes[data.read_default]}; what is gone: {meta.gone_modes[data.gone_default]}</p>
      {data.may_edit && <p className="row-gap"><button onClick={() => setDlg(data)}>Edit</button><button onClick={remove}>Delete</button></p>}
      {msg && <p className="status ok">{msg}</p>}
      <HowToRun name={data.name} />
      <h2>Sources</h2>
      {data.may_edit && <p><button className="primary" onClick={() => setSrc({})}>＋ Add a source</button></p>}
      {!data.sources.length ? <p className="quiet">No source yet.</p> : (
        <table className="grid-table small">
          <thead><tr><th>Name</th><th>Kind</th><th>Where</th><th>Includes</th><th>Attachments</th><th>Sign-in</th><th>Last test</th><th>Last run got to</th></tr></thead>
          <tbody>{data.sources.map((s) => (
            <tr key={s.id} className={s.enabled ? "" : "quiet"}>
              <td>{data.may_edit ? <button className="linkish" onClick={() => setSrc(s)}>{s.name}</button> : s.name}{!s.enabled && " (off)"}</td>
              <td>{s.kind_label}</td><td className="wrap-any">{s.location}</td><td>{s.include || "everything shared"}</td>
              <td>{s.attachments ? "read" : "not read"}</td><td>{meta.sign_ins.find((x) => x.code === s.sign_in)?.label}</td>
              <td className={s.test_ok === false ? "bad-text" : ""}>{s.tested_at ? `${s.test_ok ? "✓" : "✗"} ${fmtDateTime(s.tested_at)}` : "–"}{s.test_note && <div className="quiet">{s.test_note}</div>}</td>
              <td>{s.position || "–"}</td>
            </tr>))}</tbody>
        </table>)}
      <h2>Runs</h2>
      {!data.runs.length ? <p className="quiet">Not run yet.</p> : (
        <table className="grid-table small">
          <thead><tr><th>Run</th><th>Status</th><th>By</th><th>Read</th><th>Gone</th><th>Started</th><th>Finished</th><th>Found</th><th>Skipped</th><th>May be the same</th><th>Not found</th></tr></thead>
          <tbody>{data.runs.map((r) => (
            <tr key={r.id}>
              <td><button className="linkish" onClick={() => setRun(r.id)}>Run {r.number}</button></td>
              <td><span className={`chip small${r.status === "finished" ? " ok" : ""}`}>{r.status}</span></td>
              <td>{r.who}{r.ai_client ? ` (${r.ai_client})` : ""}</td><td>{r.read_mode}</td><td>{r.gone_mode}</td>
              <td className="nowrap">{fmtDateTime(r.started_at)}</td><td className="nowrap">{r.finished_at ? fmtDateTime(r.finished_at) : "–"}</td>
              <td>{r.counts.found ?? "–"}</td><td>{r.counts.skipped ?? "–"}</td><td>{r.counts.may_be_same ?? "–"}</td><td>{r.counts.not_found ?? "–"}</td>
            </tr>))}</tbody>
        </table>)}
      {run && <RunReport id={run} onClose={() => setRun(null)} />}
      {dlg && <ProjectDialog p={dlg} data={meta} onClose={done} />}
      {src && <SourceDialog project={data} s={src} meta={meta} onClose={done} />}
    </section>
  );
}

function SourceDialog({ project, s, meta, onClose }) {
  const base = `${URL}/${project.id}/sources`;
  const [f, setF] = useState({ kind: s.kind || "folder", name: s.name || "", location: s.location || "", include: s.include || "",
    attachments: s.attachments ?? true, sign_in: s.sign_in || "none", enabled: s.enabled ?? true });
  const [secret, setSecret] = useState({});
  const [test, setTest] = useState(null);
  const [err, setErr] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const sec = (k, v) => setSecret((x) => ({ ...x, [k]: v }));
  const kind = meta.kinds.find((k) => k.code === f.kind);
  async function save(extra = {}) {
    try { const out = await apiFetch(s.id ? `${base}/${s.id}` : base, { method: s.id ? "PUT" : "POST", body: JSON.stringify({ ...f, ...extra }) }); onClose(out.message); }
    catch (e) { setErr(e.message); }
  }
  async function remove() {
    if (!window.confirm(`Remove source ${s.name}? Found in keeps its name.`)) return;
    try { const out = await apiFetch(`${base}/${s.id}`, { method: "DELETE" }); onClose(out.message); } catch (e) { setErr(e.message); }
  }
  async function tryLink() {
    setTest({ note: "Testing..." });
    try {
      const out = await apiFetch(`${URL}/test-link`, { method: "POST",
        body: JSON.stringify({ kind: f.kind, location: f.location, sign_in: f.sign_in, secret, project: project.id, source: s.id || "" }) });
      setTest(out);
    } catch (e) { setTest({ ok: false, note: e.message }); }
    setSecret({});                                   // forgotten here too
  }
  return (
    <Modal title={s.id ? `Source ${s.name}` : "Add a source"} onClose={() => onClose()} wide
      actions={<>{s.id && <button onClick={remove}>Remove</button>}{s.id && <button onClick={() => save({ reset_position: true })} title="The next run reads everything again">Read all next time</button>}
        <button onClick={() => onClose()}>Cancel</button><button className="primary" onClick={() => save()}>Save</button></>}>
      {err && <p className="status bad">{err}</p>}
      <div className="row-gap">
        <Field label="Kind"><select value={f.kind} onChange={(e) => set("kind", e.target.value)}>
          {meta.kinds.map((k) => <option key={k.code} value={k.code}>{k.label}</option>)}</select></Field>
        <Field label="Name"><input value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
      </div>
      <Field label="Where it is" hint={kind ? `for example ${kind.where}` : ""}><input value={f.location} onChange={(e) => set("location", e.target.value)} /></Field>
      <Field label="What to include" tip="Folders, labels, channels, file kinds or dates the AI reads; empty: everything the source shares. The organisation decides what each source shares.">
        <textarea rows={2} value={f.include} onChange={(e) => set("include", e.target.value)} /></Field>
      <div className="row-gap">
        <label className="check"><input type="checkbox" checked={f.attachments} onChange={(e) => set("attachments", e.target.checked)} /> Read attachments</label>
        <label className="check"><input type="checkbox" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} /> In the next runs</label>
        <Field label="Sign-in"><select value={f.sign_in} onChange={(e) => set("sign_in", e.target.value)}>
          {meta.sign_ins.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}</select></Field>
      </div>
      <fieldset className="disc-test">
        <legend>Test the link</legend>
        <p className="small quiet">Type the sign-in to test that the source answers. It is used once and forgotten: only the
          method and the result are kept. At run time your AI brings its own access.</p>
        {(f.sign_in === "key" || f.sign_in === "sso") && <Field label="Key or token"><input type="password" autoComplete="off" value={secret.token || ""} onChange={(e) => sec("token", e.target.value)} /></Field>}
        {f.sign_in === "basic" && <div className="row-gap">
          <Field label="User name"><input autoComplete="off" value={secret.username || ""} onChange={(e) => sec("username", e.target.value)} /></Field>
          <Field label="Password"><input type="password" autoComplete="off" value={secret.password || ""} onChange={(e) => sec("password", e.target.value)} /></Field></div>}
        {f.sign_in === "certificate" && <div className="row-gap">
          <Field label="Certificate (PEM)"><textarea rows={3} value={secret.certificate || ""} onChange={(e) => sec("certificate", e.target.value)} /></Field>
          <Field label="Private key (PEM)"><textarea rows={3} value={secret.private_key || ""} onChange={(e) => sec("private_key", e.target.value)} /></Field></div>}
        <button onClick={tryLink} disabled={!f.location}>Test the link</button>
        {test && <p className={`status${test.ok === undefined ? "" : test.ok ? " ok" : " bad"}`}>{test.note}{test.kept ? ` ${test.kept}` : ""}</p>}
      </fieldset>
    </Modal>
  );
}

function RunReport({ id, onClose }) {
  const { data, error } = useApi(`/api/v1/discovery-runs/${id}`);
  const [tab, setTab] = useState("found");
  async function dealt(f) {
    try { await apiFetch(`/api/v1/discovery-runs/${id}/may-be-same/${f}`, { method: "POST" }); refreshAll(); } catch { /* shown on reload */ }
  }
  const el = (mid, eid, name) => (eid ? <a href={`#/metamodel/${mid}/entity/${eid}`}>{name}</a> : name);
  return (
    <Modal title={data ? `${data.project.name}: run ${data.run.number}` : "Discovery run"} onClose={onClose} wide
      actions={<button onClick={onClose}>Close</button>}>
      {error && <p className="status bad">{error}</p>}
      {!data ? <p className="quiet">Loading...</p> : (<>
        <p className="small">{data.run.who}{data.run.ai_client ? ` (${data.run.ai_client})` : ""} · read {data.run.read_mode} · gone: {data.run.gone_mode} ·
          {" "}{fmtDateTime(data.run.started_at)}{data.run.finished_at ? ` to ${fmtDateTime(data.run.finished_at)}` : " (running)"}
          {data.compare && <> · <a href={data.compare} onClick={onClose}>Compare the run's tags (what it changed, the metamodel first)</a></>}</p>
        {data.run.summary && <p className="pre-wrap">{data.run.summary}</p>}
        <div className="tabs sub" role="tablist">
          {[["found", `Found (${data.found.length})`], ["skipped", `Skipped as NOT FOR AI (${data.skipped.length})`],
            ["same", `May be the same (${data.may_be_same.length})`], ["gone", `Not found (${data.not_found.length})`]].map(([k, l]) => (
            <button key={k} className={`tab${tab === k ? " on" : ""}`} onClick={() => setTab(k)}>{l}</button>))}
        </div>
        {tab === "found" && <table className="grid-table small"><thead><tr><th>Element</th><th>Kind</th><th>Source</th><th>Item</th><th>Where in it</th></tr></thead>
          <tbody>{data.found.map((f, i) => (<tr key={i}><td>{f.kind === "entity" ? el(data.target_model.id, f.element_id, f.element_name || f.element_ref) : f.element_ref}</td>
            <td>{f.kind}</td><td>{f.source}</td><td>{safeLink(f.link) ? <a href={safeLink(f.link)} target="_blank" rel="noopener noreferrer">{f.item || "open"}</a> : f.item}</td><td>{f.place}</td></tr>))}</tbody></table>}
        {tab === "skipped" && (data.skipped.length ? <table className="grid-table small"><thead><tr><th>Title</th><th>Source</th><th>Where</th><th>Date</th><th>Why</th></tr></thead>
          <tbody>{data.skipped.map((s, i) => <tr key={i}><td>{s.title}</td><td>{s.source}</td><td>{s.place}</td><td>{s.date}</td><td>{s.reason}</td></tr>)}</tbody></table>
          : <p className="quiet">Nothing was skipped.</p>)}
        {tab === "same" && (data.may_be_same.length ? <>
          <p className="small quiet">The AI was unsure whether these are the same: merge them with the model's Dedupe, or keep them apart, then mark them dealt with.</p>
          <table className="grid-table small"><thead><tr><th>Found</th><th>May be the same as</th><th>Note</th><th></th></tr></thead>
            <tbody>{data.may_be_same.map((s) => <tr key={s.id}><td>{el(data.target_model.id, s.element_id, s.element_ref)}</td>
              <td>{el(data.target_model.id, s.other_id, s.other_ref)}</td><td>{s.note}</td>
              <td>{s.resolved_at ? `dealt with by ${s.resolved_by}` : <button onClick={() => dealt(s.id)}>Dealt with</button>}</td></tr>)}</tbody></table></>
          : <p className="quiet">No doubts.</p>)}
        {tab === "gone" && (data.not_found.length ? <table className="grid-table small"><thead><tr><th>Element</th><th>Source</th><th>What was done</th></tr></thead>
          <tbody>{data.not_found.map((g, i) => <tr key={i}><td>{g.action === "deleted" ? g.element_name : el(data.target_model.id, g.element_id, g.element_name)}</td>
            <td>{g.source}</td><td>{g.action === "deleted" ? "Deleted" : "Marked not found"}</td></tr>)}</tbody></table>
          : <p className="quiet">Everything was still found.</p>)}
      </>)}
    </Modal>
  );
}

// an element's "Found in": where discovery runs found it
export function FoundIn({ model, entity }) {
  const { data, error } = useApi(`/api/v1/models/${model}/entities/${entity}/found-in`);
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet">Loading...</p>;
  return (
    <div>
      {data.not_found_since && <p className="status bad">Not found by run {data.not_found_since.run_number} of {data.not_found_since.project}
        {data.not_found_since.action === "deleted" ? " (deleted)" : " (marked)"}.</p>}
      {!data.found_in.length ? <p className="quiet">No discovery run found this element: it was added by a person.</p> : (
        <table className="grid-table small">
          <thead><tr><th>Source</th><th>Item</th><th>Where in it</th><th>Run</th><th>By</th><th>When</th></tr></thead>
          <tbody>{data.found_in.map((f, i) => (
            <tr key={i}><td>{f.source}</td>
              <td>{safeLink(f.link) ? <a href={safeLink(f.link)} target="_blank" rel="noopener noreferrer">{f.item || "open"}</a> : f.item}</td>
              <td>{f.place}</td><td><a href={`#/discovery-projects/${f.project_id}`}>{f.project}</a> run {f.run_number}</td>
              <td>{f.who}</td><td className="nowrap">{fmtDateTime(f.created_at)}</td></tr>))}</tbody>
        </table>)}
    </div>
  );
}
