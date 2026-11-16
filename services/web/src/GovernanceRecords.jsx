// Architecture decision records and dispensations (R5.5.1; owner, 15 Nov 2026, 18:20 with a feature specification;
// agreed 20:31 to 20:34): the two templates' fields in a record's dialog, a record's links both ways, the
// organisation's own Governance Log (#/governance, the Architecture Board accepts), dispensations ending soon, the
// governance report, and an element's "Linked decisions and dispensations".
import { useState } from "react";
import { apiFetch } from "./auth";
import { Field, Modal } from "./ModelOps";
import { refreshAll, useApi } from "./ModelViews";
import RichText from "./RichText";
import { fmtDateTime } from "./fmt";

export const ADR = "Architecture Decision Record";
export const DISP = "Dispensation";
export const YEARLY = [ADR, DISP];
const rich = (v) => (v ? <div className="rich-view" dangerouslySetInnerHTML={{ __html: v }} /> : <span className="quiet">–</span>);

// the template's own fields and the record's ADM phase, record type and sponsor
export function TemplateFields({ f, set, can }) {
  const { data: t } = useApi("/api/v1/governance/templates");
  if (!YEARLY.includes(f.kind) || !t) return null;
  const tpl = t[f.kind];
  const fields = f.fields || {};
  const setField = (k, v) => set("fields", { ...fields, [k]: v });
  const req = (on) => (on ? <span className="bad-text" title="Required before it is proposed"> *</span> : null);
  return (
    <div className="gov-template">
      <div className="row-gap">
        <Field label="ADM phase"><select value={f.phase || ""} onChange={(e) => set("phase", e.target.value)} disabled={!can}>
          <option value="">–</option>{t.phases.map((x) => <option key={x} value={x}>{x.length === 1 ? `Phase ${x}` : x}</option>)}</select></Field>
        {f.kind === ADR && <Field label={<>Record type{req(true)}</>}><select value={f.record_type || ""} onChange={(e) => set("record_type", e.target.value)} disabled={!can}>
          <option value="">–</option>{t.record_types.map((x) => <option key={x}>{x}</option>)}</select></Field>}
        {f.kind === DISP && <Field label={<>Sponsor{req(true)}</>}><input value={f.sponsor || ""} onChange={(e) => set("sponsor", e.target.value)} disabled={!can} /></Field>}
      </div>
      {tpl.fields.map((x) => (
        <Field key={x.name} label={<>{x.label}{req(x.required)}</>}>
          {x.kind === "long"
            ? <textarea rows={3} value={fields[x.name] || ""} onChange={(e) => setField(x.name, e.target.value)} disabled={!can} />
            : <input value={fields[x.name] || ""} onChange={(e) => setField(x.name, e.target.value)} disabled={!can} />}
        </Field>))}
      <p className="small quiet">Fields marked * are needed before it is proposed for acceptance{f.kind === DISP ? ", with its expiry date" : ""}.</p>
    </div>
  );
}

const KINDS = [["element", "An element of a model"], ["requirement", "A stakeholder requirement (an element)"], ["principle", "A principle"],
  ["standard", "A standard"], ["record", "Another record"]];
const RELATIONS = { element: ["affects"], requirement: ["meets"], principle: ["governed-by"], standard: ["governed-by"], record: ["supersedes", "depends-on"] };
const WORD = { affects: "affects", meets: "meets", "governed-by": "governed by", supersedes: "supersedes", "depends-on": "depends on",
  "superseded-by": "superseded by", "depended-on-by": "depended on by" };

// a record's links both ways (R5.5.1 (2)): to elements, requirements, principles, standards and other records
export function RecordLinks({ rid, can, principles = [], standards = [], records = [] }) {
  const url = `/api/v1/governance/records/${rid}/links`;
  const { data } = useApi(url);
  const [add, setAdd] = useState(null);
  const [hits, setHits] = useState([]);
  const [err, setErr] = useState("");
  async function find(q) {
    setAdd((a) => ({ ...a, q }));
    if (q.trim().length < 2) { setHits([]); return; }
    try { const r = await apiFetch(`/api/v1/search?q=${encodeURIComponent(q)}&limit=20${add?.kind === "requirement" ? "&type=Requirement" : ""}`); setHits(r.results || []); }
    catch (e) { setErr(e.message); }
  }
  async function link(target, model) {
    setErr("");
    try { await apiFetch(url, { method: "POST", body: JSON.stringify({ kind: add.kind, relation: add.relation, target, model }) }); setAdd(null); setHits([]); refreshAll(); }
    catch (e) { setErr(e.message); }
  }
  async function unlink(id) {
    try { await apiFetch(`${url}/${id}`, { method: "DELETE" }); refreshAll(); } catch (e) { setErr(e.message); }
  }
  if (!data) return null;
  return (
    <div className="gov-links">
      <h4>Links</h4>
      {err && <p className="status bad small">{err}</p>}
      {!data.links.length && !data.linked_from.length ? <p className="small quiet">Not linked to anything yet.</p> : (
        <ul className="small">
          {data.links.map((l) => <li key={l.id}>{WORD[l.relation]} <b>{l.label}</b> <span className="quiet">({l.kind})</span>
            {can && <button className="linkish small" onClick={() => unlink(l.id)} aria-label={`Remove the link to ${l.label}`}>remove</button>}</li>)}
          {data.linked_from.map((b) => <li key={b.id}>{WORD[b.relation]} <b>{b.ref} {b.title}</b> <span className="quiet">({b.status})</span></li>)}
        </ul>)}
      {can && !add && <button className="small" onClick={() => setAdd({ kind: "element", relation: "affects", q: "" })}>＋ Link</button>}
      {can && add && (
        <div className="row-gap small">
          <select value={add.kind} onChange={(e) => { setAdd({ kind: e.target.value, relation: RELATIONS[e.target.value][0], q: "" }); setHits([]); }} aria-label="Link to">
            {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          {RELATIONS[add.kind].length > 1 && <select value={add.relation} onChange={(e) => setAdd({ ...add, relation: e.target.value })} aria-label="How">
            {RELATIONS[add.kind].map((r) => <option key={r} value={r}>{WORD[r]}</option>)}</select>}
          {(add.kind === "element" || add.kind === "requirement") && <>
            <input type="search" value={add.q} onChange={(e) => find(e.target.value)} placeholder="Find the element by name" aria-label="Find the element" autoFocus />
            {hits.length > 0 && <ul className="gov-hits">{hits.map((h) => <li key={h.id}><button className="linkish" onClick={() => link(h.id, h.model_id)}>
              {h.name} <span className="quiet">({h.entity_type}, {h.model})</span></button></li>)}</ul>}</>}
          {add.kind === "principle" && <select onChange={(e) => e.target.value && link(e.target.value)} defaultValue="" aria-label="Principle"><option value="">Choose…</option>
            {principles.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>}
          {add.kind === "standard" && <select onChange={(e) => e.target.value && link(e.target.value)} defaultValue="" aria-label="Standard"><option value="">Choose…</option>
            {standards.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>}
          {add.kind === "record" && <select onChange={(e) => e.target.value && link(e.target.value)} defaultValue="" aria-label="Record"><option value="">Choose…</option>
            {records.filter((x) => x.id !== rid).map((x) => <option key={x.id} value={x.id}>{x.ref} {x.title}</option>)}</select>}
          <button className="small" onClick={() => { setAdd(null); setHits([]); }}>Cancel</button>
        </div>)}
    </div>
  );
}

// dispensations ending soon (R5.5.1 (4)): on the organisation's log and on a project's governance tab
export function EndingSoon({ project }) {
  const { data } = useApi("/api/v1/governance/ending-soon");
  const rows = (data?.dispensations || []).filter((r) => !project || r.project === project);
  if (!rows.length) return null;
  return (
    <div className="status warn gov-ending">
      <b>Dispensations ending within {data.days} days:</b>{" "}
      {rows.map((r, i) => <span key={r.id}>{i ? "; " : ""}{r.ref} {r.title} ({r.project_name}, {r.expires_on}, {r.days_left} day{r.days_left === 1 ? "" : "s"})</span>)}
    </div>
  );
}

// the organisation's own Governance Log (#/governance): the Architecture Board accepts or rejects
export default function OrgGovernance() {
  const url = "/api/v1/governance";
  const { data, error } = useApi(url);
  const [tab, setTab] = useState("log");
  const [kind, setKind] = useState("*");
  const [dlg, setDlg] = useState(null);
  const [msg, setMsg] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet">Loading...</p>;
  const recs = data.records.filter((r) => kind === "*" || r.kind === kind);
  return (
    <section>
      <h1>Governance Log</h1>
      <p className="quiet">The organisation's own architecture decision records and dispensations, outside any project. The
        Architecture Board accepts or rejects them; in a project, its sign-off people do (the project's Governance tab).
        Each dispensation needs an expiry date: its owner, sponsor and the Board are told before it ends and on the day.</p>
      {msg && <p className="status ok">{msg}</p>}
      <EndingSoon />
      <div className="tabs sub" role="tablist">
        <button className={`tab${tab === "log" ? " on" : ""}`} onClick={() => setTab("log")}>The log</button>
        <button className={`tab${tab === "report" ? " on" : ""}`} onClick={() => setTab("report")}>Report (every project)</button>
      </div>
      {tab === "report" ? <GovernanceReport /> : (<>
        <div className="row-gap filters">
          {data.may_edit && <button className="primary" onClick={() => setDlg({ kind: ADR })}>＋ Log an ADR</button>}
          {data.may_edit && <button onClick={() => setDlg({ kind: DISP })}>＋ Log a dispensation</button>}
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind"><option value="*">Every kind</option>
            <option value={ADR}>ADRs</option><option value={DISP}>Dispensations</option></select>
        </div>
        {!recs.length ? <p className="quiet">Nothing logged yet.</p> : (
          <table className="grid-table">
            <thead><tr><th>Ref</th><th>Title</th><th>Kind</th><th>Status</th><th>Phase</th><th>Owner</th><th>Date</th><th>Ends / review</th><th>Links</th></tr></thead>
            <tbody>{recs.map((r) => (
              <tr key={r.id}>
                <td className="nowrap"><button className="linkish" onClick={() => setDlg(r)}>{r.ref}</button></td>
                <td><button className="linkish" onClick={() => setDlg(r)}>{r.title}</button>{r.found_in && <span className="chip small" title="Found by the discovery AI">AI</span>}</td>
                <td className="small">{r.kind === ADR ? "ADR" : r.kind}</td><td><span className="chip small">{r.status}</span></td>
                <td className="small">{r.phase}</td><td className="small">{r.owner}</td><td className="small nowrap">{r.raised_on}</td>
                <td className={`small nowrap${r.overdue ? " status bad" : ""}`}>{r.expires_on}</td><td className="small">{r.links}</td>
              </tr>))}</tbody>
          </table>)}
      </>)}
      {dlg && <OrgDialog url={url} r={dlg} data={data} onClose={(m) => { setDlg(null); if (m) { setMsg(m); refreshAll(); } }} />}
    </section>
  );
}

function OrgDialog({ url, r, data, onClose }) {
  const can = data.may_edit;
  const k = data.kinds.find((x) => x.name === r.kind) || data.kinds[0];
  const [f, setF] = useState({ kind: r.kind, title: r.title || "", html: r.html || "", status: r.status || k.statuses[0], owner: r.owner || "",
    sponsor: r.sponsor || "", phase: r.phase || "", record_type: r.record_type || "", raised_on: r.raised_on || new Date().toISOString().slice(0, 10),
    expires_on: r.expires_on || "", fields: r.fields || {} });
  const [err, setErr] = useState("");
  const [why, setWhy] = useState("");
  const set = (key, v) => setF((x) => ({ ...x, [key]: v }));
  async function save() {
    try { const out = await apiFetch(r.id ? `${url}/${r.id}` : url, { method: r.id ? "PUT" : "POST", body: JSON.stringify(f) }); refreshAll(); onClose(out.message); }
    catch (e) { setErr(e.message); }
  }
  async function decide(action) {
    try { const out = await apiFetch(`${url}/${r.id}/decision`, { method: "POST", body: JSON.stringify({ action, comment: why }) }); refreshAll(); onClose(out.message); }
    catch (e) { setErr(e.message); }
  }
  return (
    <Modal title={r.id ? `${r.ref} ${r.title}` : `Log ${f.kind === ADR ? "an ADR" : "a dispensation"}`} onClose={() => onClose()} wide
      actions={<><button onClick={() => onClose()}>{can ? "Cancel" : "Close"}</button>{can && <button className="primary" disabled={!f.title.trim()} onClick={save}>Save</button>}</>}>
      {err && <p className="status bad">{err}</p>}
      <div className="ed-form">
        <Field label="Title"><input value={f.title} onChange={(e) => set("title", e.target.value)} disabled={!can} autoFocus /></Field>
        <div className="row-gap">
          <Field label="Status"><select value={f.status} onChange={(e) => set("status", e.target.value)} disabled={!can}>{k.statuses.map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Owner"><input value={f.owner} onChange={(e) => set("owner", e.target.value)} disabled={!can} /></Field>
          <Field label="Date"><input type="date" value={f.raised_on} onChange={(e) => set("raised_on", e.target.value)} disabled={!can} /></Field>
          <Field label={f.kind === DISP ? "Expires" : "Review"}><input type="date" value={f.expires_on} onChange={(e) => set("expires_on", e.target.value)} disabled={!can} /></Field>
        </div>
        <TemplateFields f={f} set={set} can={can} />
        <Field label="Detail">{can ? <RichText value={f.html} onChange={(v) => set("html", v)} placeholder="Anything more" /> : rich(f.html)}</Field>
        {r.id && <p className="small quiet">Logged by {r.created_by}; last changed by {r.modified_by}.{r.approved_by ? ` Accepted by ${r.approved_by}, ${fmtDateTime(r.approved_at)}.` : ""}</p>}
        {r.found_in && <p className="small quiet">Found in: {r.found_in.item || r.found_in.source} {r.found_in.where ? `(${r.found_in.where})` : ""}</p>}
      </div>
      {r.id && <RecordLinks rid={r.id} can={can} records={data.records} />}
      {r.id && data.may_accept && ["Draft", "Proposed"].includes(r.status) && (
        <div className="approval-box">
          <h4>The Architecture Board's decision</h4>
          <input value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Comment (needed to reject)" aria-label="Comment" />
          <div className="row-gap"><button className="primary" onClick={() => decide("accept")}>Accept</button>
            <button className="danger" onClick={() => decide("reject")} disabled={!why.trim()}>Reject</button></div>
        </div>)}
    </Modal>
  );
}

// the standard governance report (R5.5.1 (6)): decisions by status and project, active dispensations by expiry
export function GovernanceReport() {
  const { data, error } = useApi("/api/v1/governance/report");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet">Loading...</p>;
  const statuses = Object.keys(data.decisions_by_status);
  return (
    <div>
      <p className="small quiet">Every ADR, decision and dispensation of the projects you may read and of the organisation. In Excel or Power BI:
        the OData feed <code>/api/v1/odata/governance/</code>; in Reports: the view rpt.v_governance_decisions.</p>
      <h3>Decisions by status</h3>
      {!statuses.length ? <p className="quiet">None yet.</p> : <div className="kpi-row">{statuses.map((s) => <div key={s} className="kpi"><b>{data.decisions_by_status[s]}</b><span>{s}</span></div>)}</div>}
      <h3>Decisions by project</h3>
      <table className="grid-table small"><thead><tr><th>Project</th>{statuses.map((s) => <th key={s}>{s}</th>)}</tr></thead>
        <tbody>{Object.entries(data.decisions_by_project).map(([p, by]) => <tr key={p}><td>{p}</td>{statuses.map((s) => <td key={s}>{by[s] || ""}</td>)}</tr>)}</tbody></table>
      <h3>Active dispensations by expiry date{data.ending_soon ? ` (${data.ending_soon} ending soon)` : ""}</h3>
      {!data.active_dispensations.length ? <p className="quiet">None active.</p> : (
        <table className="grid-table small"><thead><tr><th>Ref</th><th>Title</th><th>Project</th><th>Owner</th><th>Sponsor</th><th>Expires</th><th>Days left</th></tr></thead>
          <tbody>{data.active_dispensations.map((r) => (
            <tr key={r.Id} className={r.EndingSoon ? "stuck" : ""}><td>{r.Ref}</td><td>{r.Title}</td><td>{r.Project}</td><td>{r.Owner}</td><td>{r.Sponsor}</td>
              <td className="nowrap">{r.ExpiresOn}</td><td className={r.EndingSoon ? "bad-text" : ""}>{r.DaysLeft}</td></tr>))}</tbody></table>)}
    </div>
  );
}

// an element's "Linked decisions and dispensations" tab (R5.5.1 (2))
export function ElementDecisions({ model, entity }) {
  const { data, error } = useApi(`/api/v1/models/${model}/entities/${entity}/decisions`);
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet">Loading...</p>;
  if (!data.records.length) return <p className="quiet">No decision record or dispensation is linked to this element.</p>;
  return (
    <table className="grid-table small">
      <thead><tr><th>Ref</th><th>Title</th><th>Kind</th><th>Status</th><th>Where</th><th>Ends</th></tr></thead>
      <tbody>{data.records.map((r) => (
        <tr key={r.id} className={r.ending_soon ? "stuck" : ""}>
          <td className="nowrap"><a href={r.project ? `#/projects/${r.project}/governance?kind=${encodeURIComponent(r.kind)}` : "#/governance"}>{r.ref}</a></td>
          <td>{r.title}</td><td>{r.kind === ADR ? "ADR" : r.kind}</td>
          <td><span className={`chip small${r.active ? " ok" : ""}`}>{r.status}</span></td><td>{r.project_name}</td>
          <td className={`nowrap${r.ending_soon ? " bad-text" : ""}`}>{r.expires_on}{r.ending_soon ? " (ending soon)" : ""}</td>
        </tr>))}</tbody>
    </table>
  );
}
