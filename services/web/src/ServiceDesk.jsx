// The service desk (R5.11, D692): #/service-desk[/<tab>|/REQ-n]
//   ask        a group, then what you need in it (or "Something else"), then its form; sent to the Super Admins as REQ-<n>
//              (R5.27, D700)
//   mine       what I asked for
//   queue      Super Admins: what nobody has yet and what is theirs; everyone else: what is assigned to them
//   all        every request (Super Admins, Auditors), with the figures
//   catalogue  the request types: add, change, switch off (Super Admin)
//   REQ-n      one request: its details, the conversation, files; a Super Admin assigns it; the person on it does it
import { useEffect, useState } from "react";
import { apiDownload, apiFetch, apiUpload, can, roles } from "./auth";
import { fmtDateTime } from "./fmt";

const STATUS = { new: "New", "waiting-approval": "Waiting for approval", approved: "Approved", "in-progress": "In progress",
  "waiting-requester": "Waiting for you", done: "Done", declined: "Declined", cancelled: "Cancelled" };

export default function ServiceDesk({ route }) {
  const part = route.replace(/^#\/service-desk\/?/, "").split("?")[0];
  if (/^REQ-\d+$/i.test(part)) return <TicketPage ident={part.toUpperCase()} />;
  const tab = part || "ask";
  const tabs = [["ask", "Ask for something"], ["mine", "My requests"], ["queue", roles().includes("super-admin") ? "To assign and work on" : "Assigned to me"],
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

// Ask (R5.27, D700): 1 a group, 2 what you need in it (or "Something else"), 3 the details. Every request goes to
// the Super Admins, who assign it to someone.
function Ask() {
  const [cat, setCat] = useState(null);
  const [group, setGroup] = useState("");
  const [pick, setPick] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { apiFetch("/api/v1/service-desk/catalogue").then(setCat).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="status bad">{err}</p>;
  if (!cat) return <p><span className="spinner" aria-hidden="true" /> Reading the catalogue…</p>;
  const other = cat.types.find((t) => t.key === cat.other);
  const inGroup = cat.types.filter((t) => t.area === group && t.key !== cat.other);
  const steps = [["Group", () => { setGroup(""); setPick(null); }], ["Request", () => setPick(null)], ["Details", null]];
  const at = pick ? 2 : group ? 1 : 0;
  return (
    <div className="desk-ask">
      <ol className="desk-steps" aria-label="Steps">
        {steps.map(([l, go], i) => (
          <li key={l} className={i === at ? "on" : i < at ? "done" : ""}>
            {i < at && go ? <button className="linkish" onClick={go}>{i + 1}. {l}</button> : <span>{i + 1}. {l}</span>}
          </li>))}
      </ol>
      {pick ? <RequestForm type={pick} group={group} onBack={() => setPick(null)} />
        : !group ? (
          <>
            <p className="quiet">What is it about? Every request goes to the Super Admins, who pass it to the right person.</p>
            <div className="desk-cards">
              {cat.groups.map((g) => (
                <button key={g.name} className={`desk-card${g.name === "Other" ? " other" : ""}`}
                  onClick={() => (g.name === "Other" && other ? (setGroup("Other"), setPick(other)) : setGroup(g.name))}>
                  <strong>{g.name === "Other" ? "Something else" : g.name}</strong>
                  <span>{g.about}</span>
                  {g.name !== "Other" && <span className="desk-count">{g.types} kinds of request</span>}
                </button>))}
            </div>
          </>)
        : (
          <>
            <h2>{group}: what do you need?</h2>
            <div className="desk-cards">
              {inGroup.map((t) => (
                <button key={t.key} className="desk-card" onClick={() => setPick(t)}>
                  <strong>{t.name}</strong><span>{t.about}</span>
                  <span className="desk-count">usually within {t.target_hours} h</span>
                </button>))}
              {other && (
                <button className="desk-card other" onClick={() => setPick(other)}>
                  <strong>Something not listed here</strong><span>Describe what you need about {group.toLowerCase()}.</span>
                </button>)}
            </div>
          </>)}
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
  return (
    <div className="desk-field">
      <label htmlFor={`f-${f.name}`}>{f.label}{f.required && <span className="req" aria-hidden="true"> *</span>}</label>
      {input}
      {f.help && <span className="small quiet">{f.help}</span>}
    </div>);
}

function RequestForm({ type, group, onBack }) {
  const [fields, setFields] = useState({});
  const [title, setTitle] = useState(type.key === "other" ? "" : type.name);
  const [priority, setPriority] = useState("normal");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function send(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const body = { type: type.key, title: title || type.name, fields, priority, ...(type.key === "other" ? { group } : {}) };
      const t = await apiFetch("/api/v1/service-desk/tickets", { method: "POST", body: JSON.stringify(body) });
      window.location.hash = `#/service-desk/${t.number}`;
    } catch (x) { setErr(x.message); }
    setBusy(false);
  }
  return (
    <form className="desk-form" onSubmit={send}>
      <h2>{type.key === "other" ? (group && group !== "Other" ? `Something else about ${group.toLowerCase()}` : "Something else") : type.name}</h2>
      <p className="quiet">{type.about}</p>
      <div className="desk-field">
        <label htmlFor="req-title">A short title</label>
        <input id="req-title" value={title} placeholder="In a few words" onChange={(e) => setTitle(e.target.value)} />
      </div>
      {(type.form || []).map((f) => <Field key={f.name} f={f} value={fields[f.name]} onChange={(v) => setFields((x) => ({ ...x, [f.name]: v }))} />)}
      <div className="desk-field">
        <label htmlFor="req-priority">How urgent</label>
        <select id="req-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
          {[["low", "Low"], ["normal", "Normal"], ["high", "High"], ["urgent", "Urgent: I cannot work"]].map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      {err && <p className="status bad" role="alert">{err}</p>}
      <div className="desk-actions">
        <button type="button" onClick={onBack}>Back</button>
        <button type="submit" className="primary" disabled={busy}>{busy ? "Sending…" : "Send to the Super Admins"}</button>
      </div>
    </form>
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
              <td>{t.raised_by}</td><td>{t.assigned_to || <span className="quiet">Super Admins</span>}</td><td>{t.due_at ? fmtDateTime(t.due_at) : ""}{t.overdue ? " (overdue)" : ""}</td>
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
  const [people, setPeople] = useState(null);
  const [to, setTo] = useState("");
  const load = () => apiFetch(`/api/v1/service-desk/tickets/${ident}`).then(setT).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [ident]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (t?.can_assign && !people) apiFetch("/api/v1/service-desk/people").then((x) => setPeople(x.people || [])).catch(() => setPeople([]));
  }, [t?.can_assign]);   // eslint-disable-line react-hooks/exhaustive-deps
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
      setNote(""); setTo(""); load();
    } catch (e) { setErr(e.message); }
  }
  async function upload(file) {
    const fd = new FormData(); fd.append("file", file);
    try { await apiUpload(`/api/v1/service-desk/tickets/${ident}/files`, fd); load(); }
    catch (e) { setErr(e.message); }
  }
  const download = (f) => apiDownload(`/api/v1/service-desk/tickets/${ident}/files/${f.id}`, f.name).catch((e) => setErr(e.message));
  const open = !["done", "declined", "cancelled"].includes(t.status);
  const label = (k) => (k === "group" ? "Group" : (t.type?.form || []).find((f) => f.name === k)?.label || k);
  return (
    <div className="service-desk desk-ticket">
      <p className="small"><a href="#/service-desk/mine">‹ My requests</a>{t.can_work && <> · <a href="#/service-desk/queue">To work on</a></>}</p>
      <h1>{t.title} <span className="quiet">{t.number}</span></h1>
      <p><span className={`desk-status s-${t.status}`}>{STATUS[t.status]}</span>
        <span className={`desk-prio p-${t.priority}`}>{t.priority}</span>{t.overdue && <span className="desk-prio p-urgent">overdue</span>}</p>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      <div className="desk-ticket-body">
        <div className="desk-main">
          <section className="desk-box">
            <h3>What was asked</h3>
            <dl className="desk-facts">
              {Object.entries(t.fields || {}).map(([k, v]) => <div key={k}><dt>{label(k)}</dt><dd>{String(t.shown?.[k] ?? v)}</dd></div>)}
            </dl>
          </section>
          <section className="desk-box">
            <h3>Conversation and history</h3>
            <ul className="desk-events">
              {t.events.map((e) => (
                <li key={e.id} className={e.kind === "comment" ? "comment" : "event"}>
                  <span className="who">{e.by_whom}</span> <span className="small quiet">{fmtDateTime(e.at)}</span>
                  <div>{e.kind === "comment" ? e.body : <span className="quiet">{({ raised: "asked for this", assigned: `assigned it to ${e.data?.to || ""}`, status: `set it to ${STATUS[e.data?.to] || e.data?.to || ""}`, file: "added a file", priority: `set the priority to ${e.data?.priority || ""}` })[e.kind] || e.kind}{e.body ? `: ${e.body}` : ""}</span>}</div>
                </li>))}
            </ul>
            {open && (
              <div className="desk-field">
                <label htmlFor="ticket-note">Write a comment</label>
                <textarea id="ticket-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
                <div className="desk-actions"><button disabled={!note.trim()} onClick={() => act("comment")}>Send the comment</button></div>
              </div>)}
          </section>
          <section className="desk-box">
            <h3>Files</h3>
            {!t.files.length ? <p className="quiet small">None yet.</p>
              : <ul>{t.files.map((f) => <li key={f.id}><button className="linkish" onClick={() => download(f)}>{f.name}</button> <span className="small quiet">{Math.max(1, Math.round(f.size / 1024))} KB, {f.added_by}</span></li>)}</ul>}
            {open && <label className="small">Add a file (10 MB at most) <input type="file" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} /></label>}
          </section>
        </div>
        <aside className="desk-side">
          <section className="desk-box">
            <dl className="desk-facts">
              <div><dt>Asked by</dt><dd>{t.raised_by}</dd></div>
              <div><dt>Asked on</dt><dd>{fmtDateTime(t.created_at)}</dd></div>
              <div><dt>Assigned to</dt><dd>{t.assigned_to || "the Super Admins"}</dd></div>
              {t.due_at && <div><dt>Due</dt><dd>{fmtDateTime(t.due_at)}</dd></div>}
            </dl>
          </section>
          {open && t.can_assign && (
            <section className="desk-box">
              <h3>{t.assigned_to ? "Assign to someone else" : "Assign it"}</h3>
              <div className="desk-field">
                <label htmlFor="assign-to">Person</label>
                <select id="assign-to" value={to} onChange={(e) => setTo(e.target.value)}>
                  <option value="">Choose…</option>
                  {(people || []).filter((u) => u !== t.assigned_to).map((u) => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
              <div className="desk-actions">
                <button className="primary" disabled={!to} onClick={() => act("assign", { to })}>Assign</button>
                {!t.assigned_to && <button onClick={() => act("assign", {})}>Take it myself</button>}
              </div>
            </section>)}
          {open && (t.can_work || t.mine) && (
            <section className="desk-box">
              <h3>Actions</h3>
              <div className="desk-actions column">
                {t.can_approve && <button className="primary" onClick={() => act("approve")}>Approve</button>}
                {t.can_work && t.type?.wizard && <button className="primary" onClick={() => act("do")}>Do it</button>}
                {t.can_work && <button onClick={() => act("status", { status: "waiting-requester" })}>Ask the requester</button>}
                {t.can_work && <button onClick={() => act("status", { status: "done" })}>Mark it done</button>}
                {t.can_work && <button onClick={() => act("status", { status: "declined" })}>Decline</button>}
                {t.assigned_to_me && !t.can_assign && <button onClick={() => act("assign", { to: "" })}>Hand it back to the Super Admins</button>}
                {t.mine && <button onClick={() => act("cancel")}>Cancel my request</button>}
              </div>
              <p className="small quiet">A note in the comment box goes with the action.</p>
            </section>)}
        </aside>
      </div>
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
  const blank = { key: "", area: "Other", name: "", about: "", target_hours: 24, wizard: "", enabled: true, sort: 100, formText: "[]" };
  const groupNames = (cat.groups || []).map((g) => g.name);
  return (
    <div>
      <p className="quiet">What people can ask for, in groups. Each type has its own form and a target time. Every request goes to the Super Admins, who assign it.</p>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {edit ? (
        <fieldset>
          <legend>{edit.key ? `Change ${edit.name}` : "A new request type"}</legend>
          {[["key", "Key"], ["name", "Name"], ["about", "About"], ["wizard", "Wizard address (optional)"]].map(([k, l]) => (
            <p key={k}><label>{l} <input value={edit[k] || ""} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} /></label></p>))}
          <p><label>Group <input list="desk-groups" value={edit.area || ""} onChange={(e) => setEdit({ ...edit, area: e.target.value })} /></label>
            <datalist id="desk-groups">{groupNames.map((x) => <option key={x} value={x} />)}</datalist>{" "}
            <label>Target (hours) <input type="number" value={edit.target_hours} onChange={(e) => setEdit({ ...edit, target_hours: Number(e.target.value) })} /></label>{" "}
            <label><input type="checkbox" checked={edit.enabled} onChange={(e) => setEdit({ ...edit, enabled: e.target.checked })} /> On</label></p>
          <p><label>Form (fields as JSON: name, label, kind: {cat.field_kinds.join(", ")}; required; choices)<br />
            <textarea rows={8} className="wide" value={edit.formText ?? JSON.stringify(edit.form, null, 2)} onChange={(e) => setEdit({ ...edit, formText: e.target.value })} /></label></p>
          <button className="primary" onClick={save}>Save</button> <button onClick={() => setEdit(null)}>Close</button>
        </fieldset>
      ) : <p><button onClick={() => setEdit(blank)}>Add a request type</button></p>}
      <table className="grid-table small">
        <thead><tr><th>Group</th><th>Name</th><th>Target</th><th>On</th><th /></tr></thead>
        <tbody>{cat.types.map((t) => (
          <tr key={t.key} className={t.enabled ? "" : "quiet"}><td>{t.area}</td><td>{t.name}</td>
            <td>{t.target_hours} h</td><td>{t.enabled ? "yes" : "no"}</td>
            <td><button className="small" onClick={() => setEdit({ ...t, formText: JSON.stringify(t.form, null, 2) })}>Change</button></td></tr>))}</tbody>
      </table>
    </div>
  );
}
