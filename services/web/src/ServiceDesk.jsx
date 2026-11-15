// The service desk (R5.11, D692): #/service-desk[/<tab>|/REQ-n]
//   ask        the service catalogue by area; a request type's own form; sent as REQ-<n>
//   mine       what I asked for
//   queue      what my teams work on or approve (IT Admins, Model Admins of the model, ...)
//   all        every request (Super Admins, Auditors), with the figures
//   catalogue  the request types: add, change, switch off (Super Admin)
//   REQ-n      one request: its details, comments both ways, files, history; approve, assign, status, do it
import { useEffect, useState } from "react";
import { apiDownload, apiFetch, apiUpload, can, roles } from "./auth";
import { fmtDateTime } from "./fmt";

const STATUS = { new: "New", "waiting-approval": "Waiting for approval", approved: "Approved", "in-progress": "In progress",
  "waiting-requester": "Waiting for you", done: "Done", declined: "Declined", cancelled: "Cancelled" };

export default function ServiceDesk({ route }) {
  const part = route.replace(/^#\/service-desk\/?/, "").split("?")[0];
  if (/^REQ-\d+$/i.test(part)) return <TicketPage ident={part.toUpperCase()} />;
  const tab = part || "ask";
  const tabs = [["ask", "Ask for something"], ["mine", "My requests"], ["queue", "To work on"],
    ...(roles().includes("super-admin") || roles().includes("auditor") ? [["all", "All requests"]] : []),
    ...(can("settings.manage") ? [["catalogue", "Service catalogue"]] : [])];
  return (
    <div className="service-desk">
      <h1>Service desk</h1>
      <div className="tabs" role="tablist">
        {tabs.map(([k, l]) => <a key={k} href={`#/service-desk/${k}`} className={`tab${tab === k ? " on" : ""}`} role="tab" aria-selected={tab === k}>{l}</a>)}
      </div>
      <div className="tab-panel" role="tabpanel">
        {tab === "ask" ? <Ask /> : tab === "catalogue" ? <CatalogueAdmin /> : <List view={tab} />}
      </div>
    </div>
  );
}

function Ask() {
  const [cat, setCat] = useState(null);
  const [pick, setPick] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { apiFetch("/api/v1/service-desk/catalogue").then(setCat).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="status bad">{err}</p>;
  if (!cat) return <p><span className="spinner" aria-hidden="true" /> Reading the catalogue…</p>;
  if (pick) return <RequestForm type={pick} onBack={() => setPick(null)} />;
  const areas = [...new Set(cat.types.map((t) => t.area))];
  return (
    <div>
      <p className="quiet">Choose what you need. Each request goes to the team that does it, and is approved first where it must be.</p>
      {areas.map((a) => (
        <section key={a}>
          <h2>{a}</h2>
          <div className="cards">
            {cat.types.filter((t) => t.area === a).map((t) => (
              <button key={t.key} className="card" onClick={() => setPick(t)}>
                <strong>{t.name}</strong><span className="small">{t.about}</span>
                <span className="small quiet">{t.approval ? "Approved first · " : ""}within {t.target_hours} h</span>
              </button>))}
          </div>
        </section>))}
    </div>
  );
}

function Field({ f, value, onChange }) {
  const [opts, setOpts] = useState([]);
  useEffect(() => {
    if (f.kind === "model") apiFetch("/api/v1/models").then((x) => setOpts((x.models || x || []).map((m) => [m.id || m.guid, m.name]))).catch(() => {});
    if (f.kind === "project") apiFetch("/api/v1/projects").then((x) => setOpts((x.projects || x || []).map((p) => [p.guid || p.id, p.name]))).catch(() => {});
  }, [f.kind]);
  const common = { id: `f-${f.name}`, value: value || "", onChange: (e) => onChange(e.target.value), required: f.required };
  let input;
  if (f.kind === "textarea") input = <textarea rows={4} {...common} />;
  else if (f.kind === "choice") input = <select {...common}><option value="" />{f.choices.map((c) => <option key={c}>{c}</option>)}</select>;
  else if (f.kind === "model" || f.kind === "project") input = <select {...common}><option value="" />{opts.map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select>;
  else if (f.kind === "model-role") input = <select {...common}><option value="" />{["model-admin", "model-sub-admin", "committer", "architect", "history-viewer", "report-viewer"].map((r) => <option key={r}>{r}</option>)}</select>;
  else if (f.kind === "project-role") input = <select {...common}><option value="" />{["project-admin", "lead-architect", "architect", "stakeholder"].map((r) => <option key={r}>{r}</option>)}</select>;
  else if (f.kind === "global-role") input = <select {...common}><option value="" />{["super-admin", "it-admin", "user-admin", "keycloak-admin", "auditor", "model-creator", "library-admin"].map((r) => <option key={r}>{r}</option>)}</select>;
  else input = <input type={f.kind === "date" ? "date" : f.kind === "number" ? "number" : "text"} {...common} />;
  return <p><label htmlFor={`f-${f.name}`}>{f.label}{f.required ? " *" : ""}</label><br />{input}{f.help && <span className="small quiet"> {f.help}</span>}</p>;
}

function RequestForm({ type, onBack }) {
  const [fields, setFields] = useState({});
  const [title, setTitle] = useState(type.name);
  const [priority, setPriority] = useState("normal");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function send() {
    setBusy(true); setErr("");
    try {
      const t = await apiFetch("/api/v1/service-desk/tickets", { method: "POST", body: JSON.stringify({ type: type.key, title, fields, priority }) });
      window.location.hash = `#/service-desk/${t.number}`;
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }
  return (
    <div className="request-form">
      <button className="linkish" onClick={onBack}>‹ The catalogue</button>
      <h2>{type.name}</h2>
      <p className="quiet">{type.about}</p>
      <p><label htmlFor="req-title">Title</label><br /><input id="req-title" value={title} onChange={(e) => setTitle(e.target.value)} /></p>
      {(type.form || []).map((f) => <Field key={f.name} f={f} value={fields[f.name]} onChange={(v) => setFields((x) => ({ ...x, [f.name]: v }))} />)}
      <p><label htmlFor="req-priority">Priority</label><br />
        <select id="req-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>{["low", "normal", "high", "urgent"].map((p) => <option key={p}>{p}</option>)}</select></p>
      {err && <p className="status bad" role="alert">{err}</p>}
      <button className="primary" disabled={busy} onClick={send}>{busy ? "Sending…" : "Send the request"}</button>
    </div>
  );
}

function List({ view }) {
  const [status, setStatus] = useState("open");
  const [q, setQ] = useState("");
  const [d, setD] = useState(null);
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");
  const load = () => apiFetch(`/api/v1/service-desk/tickets?view=${view}&status=${status}&q=${encodeURIComponent(q)}`).then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [view, status]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (view === "all" && can("system.operate")) apiFetch("/api/v1/service-desk/stats").then(setStats).catch(() => {}); }, [view]);
  return (
    <div>
      <div className="row-gap filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="open">Open</option><option value="all">All</option>
          {Object.entries(STATUS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <input type="search" placeholder="Words or REQ-number" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
      </div>
      {stats && <p className="small">{stats.open} open · {stats.done} done in 30 days{stats.average_hours_to_done != null ? `, ${stats.average_hours_to_done} h on average` : ""} · {stats.met_target} met their target.</p>}
      {err && <p className="status bad">{err}</p>}
      {!d ? <p><span className="spinner" aria-hidden="true" /> Reading…</p> : !d.tickets.length ? <p className="quiet">No requests here.</p> : (
        <table className="grid-table">
          <thead><tr><th>Request</th><th>What</th><th>Status</th><th>Priority</th><th>Asked by</th><th>Assigned to</th><th>Due</th></tr></thead>
          <tbody>{d.tickets.map((t) => (
            <tr key={t.id} className={t.overdue ? "warn" : ""}>
              <td><a href={`#/service-desk/${t.number}`}>{t.number}</a></td><td>{t.title}</td><td>{STATUS[t.status]}</td><td>{t.priority}</td>
              <td>{t.raised_by}</td><td>{t.assigned_to || "-"}</td><td>{t.due_at ? fmtDateTime(t.due_at) : ""}{t.overdue ? " (overdue)" : ""}</td>
            </tr>))}</tbody>
        </table>)}
    </div>
  );
}

function TicketPage({ ident }) {
  const [t, setT] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [note, setNote] = useState("");
  const load = () => apiFetch(`/api/v1/service-desk/tickets/${ident}`).then(setT).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [ident]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (err && !t) return <p className="status bad">{err}</p>;
  if (!t) return <p><span className="spinner" aria-hidden="true" /> Reading the request…</p>;
  async function act(action, body = {}) {
    setErr(""); setMsg("");
    try {
      const r = await apiFetch(`/api/v1/service-desk/tickets/${ident}/${action}`, { method: "POST", body: JSON.stringify({ note, ...body }) });
      if (action === "do") {
        if (r.link) { window.location.hash = r.link; return; }
        setMsg(r.message);
      }
      setNote(""); load();
    } catch (e) { setErr(e.message); }
  }
  async function upload(file) {
    const fd = new FormData(); fd.append("file", file);
    try { await apiUpload(`/api/v1/service-desk/tickets/${ident}/files`, fd); load(); }
    catch (e) { setErr(e.message); }
  }
  const download = (f) => apiDownload(`/api/v1/service-desk/tickets/${ident}/files/${f.id}`, f.name).catch((e) => setErr(e.message));
  const open = !["done", "declined", "cancelled"].includes(t.status);
  return (
    <div className="service-desk">
      <p><a href="#/service-desk/mine">‹ My requests</a>{t.can_work && <> · <a href="#/service-desk/queue">To work on</a></>}</p>
      <h1>{t.number}: {t.title}</h1>
      <p><strong>{STATUS[t.status]}</strong> · {t.priority} · asked by {t.raised_by} on {fmtDateTime(t.created_at)} · team {t.team}
        {t.assigned_to ? ` · assigned to ${t.assigned_to}` : ""}{t.due_at ? ` · due ${fmtDateTime(t.due_at)}` : ""}{t.overdue ? " (overdue)" : ""}</p>
      {t.approval && <p className="small">Approved by: {t.approved_by ? `${t.approved_by} on ${fmtDateTime(t.approved_at)}` : `waiting for ${t.approval}`}</p>}
      <table className="grid-table small"><tbody>
        {Object.entries(t.fields || {}).map(([k, v]) => <tr key={k}><th>{(t.type?.form || []).find((f) => f.name === k)?.label || k}</th><td>{String(v)}</td></tr>)}
      </tbody></table>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {open && (
        <div className="row-gap">
          {t.can_approve && <><button className="primary" onClick={() => act("approve")}>Approve</button><button onClick={() => act("decline")}>Decline</button></>}
          {t.can_work && !t.assigned_to && <button onClick={() => act("assign")}>Take it</button>}
          {t.can_work && t.type?.wizard && <button onClick={() => act("do")}>Do it</button>}
          {t.can_work && <><button onClick={() => act("status", { status: "waiting-requester" })}>Ask the requester</button>
            <button onClick={() => act("status", { status: "done" })}>Done</button>
            <button onClick={() => act("status", { status: "declined" })}>Decline</button></>}
          {t.mine && <button onClick={() => act("cancel")}>Cancel my request</button>}
        </div>)}
      <h3>Comments and history</h3>
      <ul className="ticket-events">
        {t.events.map((e) => <li key={e.id}><span className="small quiet">{fmtDateTime(e.at)}</span> <strong>{e.by_whom}</strong> {e.kind === "comment" ? "" : `(${e.kind}${e.data?.to ? `: ${e.data.to}` : ""}) `}{e.body}</li>)}
      </ul>
      {open && (
        <p><label htmlFor="ticket-note">A comment</label><br />
          <textarea id="ticket-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} /><br />
          <button disabled={!note.trim()} onClick={() => act("comment")}>Write it</button></p>)}
      <h3>Files</h3>
      <ul>{t.files.map((f) => <li key={f.id}><button className="linkish" onClick={() => download(f)}>{f.name}</button> <span className="small quiet">{Math.round(f.size / 1024)} KB, {f.added_by}</span></li>)}</ul>
      {open && <p><label>Add a file (10 MB at most) <input type="file" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} /></label></p>}
    </div>
  );
}

function CatalogueAdmin() {
  const [cat, setCat] = useState(null);
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => apiFetch("/api/v1/service-desk/catalogue?all=1").then(setCat).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (!cat) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading…</p>;
  async function save() {
    setErr(""); setMsg("");
    try {
      const form = typeof edit.formText === "string" ? JSON.parse(edit.formText) : edit.form;
      await apiFetch(`/api/v1/service-desk/catalogue/${encodeURIComponent(edit.key)}`, { method: "PUT", body: JSON.stringify({ ...edit, form, formText: undefined }) });
      setMsg(`Saved ${edit.name}.`); setEdit(null); load();
    } catch (e) { setErr(e.message); }
  }
  const blank = { key: "", area: "Help", name: "", about: "", team: "super-admin", approval: "", target_hours: 24, wizard: "", enabled: true, sort: 100, formText: "[]" };
  return (
    <div>
      <p className="quiet">What people can ask for. Each type has its own form, the team that does it, an approval if needed and a target time.</p>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {edit ? (
        <fieldset>
          <legend>{edit.key ? `Change ${edit.name}` : "A new request type"}</legend>
          {[["key", "Key"], ["area", "Area"], ["name", "Name"], ["about", "About"], ["wizard", "Wizard address (optional)"]].map(([k, l]) => (
            <p key={k}><label>{l} <input value={edit[k] || ""} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} /></label></p>))}
          <p><label>Team <select value={edit.team} onChange={(e) => setEdit({ ...edit, team: e.target.value })}>{cat.teams.map((x) => <option key={x}>{x}</option>)}</select></label>{" "}
            <label>Approval <select value={edit.approval} onChange={(e) => setEdit({ ...edit, approval: e.target.value })}><option value="">none</option>{cat.teams.map((x) => <option key={x}>{x}</option>)}</select></label>{" "}
            <label>Target (hours) <input type="number" value={edit.target_hours} onChange={(e) => setEdit({ ...edit, target_hours: Number(e.target.value) })} /></label>{" "}
            <label><input type="checkbox" checked={edit.enabled} onChange={(e) => setEdit({ ...edit, enabled: e.target.checked })} /> On</label></p>
          <p><label>Form (fields as JSON: name, label, kind: {cat.field_kinds.join(", ")}; required; choices)<br />
            <textarea rows={8} className="wide" value={edit.formText ?? JSON.stringify(edit.form, null, 2)} onChange={(e) => setEdit({ ...edit, formText: e.target.value })} /></label></p>
          <button className="primary" onClick={save}>Save</button> <button onClick={() => setEdit(null)}>Close</button>
        </fieldset>
      ) : <p><button onClick={() => setEdit(blank)}>Add a request type</button></p>}
      <table className="grid-table small">
        <thead><tr><th>Area</th><th>Name</th><th>Team</th><th>Approval</th><th>Target</th><th>On</th><th /></tr></thead>
        <tbody>{cat.types.map((t) => (
          <tr key={t.key} className={t.enabled ? "" : "quiet"}><td>{t.area}</td><td>{t.name}</td><td>{t.team}</td><td>{t.approval || "-"}</td>
            <td>{t.target_hours} h</td><td>{t.enabled ? "yes" : "no"}</td>
            <td><button className="small" onClick={() => setEdit({ ...t, formText: JSON.stringify(t.form, null, 2) })}>Change</button></td></tr>))}</tbody>
      </table>
    </div>
  );
}
