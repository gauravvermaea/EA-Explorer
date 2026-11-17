// System Admin › Site pairings (Release 6.5, D749; owner, 17 Nov 2026, 19:30 to 19:40). Two EA Explorer sites paired one
// way: Site 1 sends, Site 2 takes. On Site 2 a Super Admin makes a pairing key; on Site 1 a Super Admin gives Site 2's
// address and the key and chooses content sync (models, projects, the organisation's content) or DR sync (all that,
// with the users and their roles; Site 2 read only). Site 2 accepts. Batches go in order, each answered; Site 2 commits
// them by hand (looking first) or by itself (DR always by itself). A DR copy takes over by stopping its pairing; failing
// back is pairing the other way. The site's purpose (PROD by default) is a label set on System settings.
import { useState } from "react";
import { apiFetch } from "./auth";
import { useApi } from "./ModelViews";
import { Field, Modal } from "./ModelOps";
import { fmtDateTime } from "./fmt";

const post = (path, body, method = "POST") => apiFetch(path, { method, body: JSON.stringify(body || {}) });
const STATUS = { key: "key made: waiting for the sending site", waiting: "waiting to be accepted", accepted: "paired",
  refused: "refused", stopped: "stopped" };
const KIND = { content: "Content sync", dr: "DR sync" };
const BATCH = { queued: "queued", sending: "sending", sent: "sent", failed: "failed", received: "received",
  waiting: "waiting for a Super Admin", committing: "being committed", committed: "committed", discarded: "discarded" };

function Scope({ value, onChange }) {
  const { data: models } = useApi("/api/v1/models");
  const { data: plist } = useApi("/api/v1/projects");
  const ms = (Array.isArray(models) ? models : models?.models || []).filter((m) => m.kind !== "template");
  const ps = plist?.projects || [];
  const all = value?.all !== false;
  const pick = (k, id) => {
    const cur = new Set(value?.[k] || []);
    if (cur.has(id)) cur.delete(id); else cur.add(id);
    onChange({ ...value, all: false, [k]: [...cur] });
  };
  return (
    <div>
      <label className="check"><input type="radio" checked={all} onChange={() => onChange({ all: true })} /> The entire site</label>
      <label className="check"><input type="radio" checked={!all} onChange={() => onChange({ all: false, models: [], projects: [], organisation: false })} /> Chosen models and projects</label>
      {!all && (
        <div className="pairing-scope">
          <div><b>Models</b>{ms.map((m) => (
            <label key={m.id} className="check small"><input type="checkbox" checked={(value.models || []).includes(String(m.id))}
              onChange={() => pick("models", String(m.id))} /> {m.name}</label>))}</div>
          <div><b>Projects</b>{ps.map((p) => (
            <label key={p.guid || p.id} className="check small"><input type="checkbox" checked={(value.projects || []).includes(String(p.guid || p.id))}
              onChange={() => pick("projects", String(p.guid || p.id))} /> {p.name}</label>))}</div>
          <label className="check small"><input type="checkbox" checked={!!value.organisation}
            onChange={() => onChange({ ...value, organisation: !value.organisation })} /> The organisation's content (its own views, templates, skills, the board, the library)</label>
        </div>)}
    </div>
  );
}

function PairDialog({ onClose, onDone }) {
  const [d, setD] = useState({ name: "", url: "https://", key: "", kind: "content", send_mode: "manual", every_minutes: 60, scope: { all: true }, trust: "" });
  const [cert, setCert] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setD({ ...d, [k]: v });
  async function check() {
    setErr("");
    try { setCert(await apiFetch(`/api/v1/pairings/certificate?url=${encodeURIComponent(d.url)}`)); } catch (e) { setErr(e.message); }
  }
  async function save() {
    setBusy(true); setErr("");
    try { await post("/api/v1/pairings", d); onDone(); } catch (e) { setErr(e.message); setBusy(false); }
  }
  return (
    <Modal title="Pair with a site" wide onClose={onClose}
      actions={<><button onClick={onClose}>Cancel</button><button className="primary" disabled={busy || !d.name || !d.key} onClick={save}>{busy ? "Pairing..." : "Pair"}</button></>}>
      <div className="ed-form">
        <p className="quiet small">This site sends; the other site takes what is sent over its own. Make the key on the other site first
          (System Admin › Site pairings › Make a key) and paste it here.</p>
        <Field label="Name"><input value={d.name} onChange={(e) => set("name", e.target.value)} placeholder="DR site, Johannesburg" /></Field>
        <Field label="The other site's address"><input value={d.url} onChange={(e) => set("url", e.target.value)} placeholder="https://ea-dr.example.com" /></Field>
        <Field label="Pairing key" hint="(made on the other site, shown there once)"><input value={d.key} onChange={(e) => set("key", e.target.value)} autoComplete="off" /></Field>
        <Field label="What is sent">
          <select value={d.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="content">Content sync: models, projects and content; the other site commits by hand or by itself</option>
            <option value="dr">DR sync: content, users and roles; committed by itself; the other site is read only</option>
          </select>
        </Field>
        {d.kind === "content" && (
          <Field label="When">
            <select value={d.send_mode} onChange={(e) => set("send_mode", e.target.value)}>
              <option value="manual">By hand (Sync now)</option>
              <option value="auto">By itself: what changed, every few minutes</option>
            </select>
          </Field>)}
        {(d.kind === "dr" || d.send_mode === "auto") && (
          <Field label="Every (minutes)"><input type="number" min={5} max={10080} value={d.every_minutes} onChange={(e) => set("every_minutes", Number(e.target.value))} /></Field>)}
        {d.kind === "content" && <Field label="What"><Scope value={d.scope} onChange={(v) => set("scope", v)} /></Field>}
        <Field label="The other site's certificate" tip="Only when it is not one this site trusts (a laptop's own): compare the fingerprint with the one the other site shows on its Site pairings page, then trust it.">
          <span><button onClick={check} disabled={!d.url.startsWith("https://")}>Read its fingerprint</button>
            {cert && <> <code className="small">{cert.sha256}</code> <label className="check small"><input type="checkbox" checked={d.trust === cert.sha256}
              onChange={(e) => set("trust", e.target.checked ? cert.sha256 : "")} /> It matches: trust it</label></>}</span>
        </Field>
        {err && <p className="status bad">{err}</p>}
      </div>
    </Modal>
  );
}

function KeyDialog({ onClose, onDone }) {
  const [name, setName] = useState("");
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  async function make() {
    setErr("");
    try { setOut(await post("/api/v1/pairings/keys", { name })); } catch (e) { setErr(e.message); }
  }
  return (
    <Modal title="Make a pairing key" onClose={() => { if (out) onDone(); onClose(); }}
      actions={out ? <button className="primary" onClick={() => { onDone(); onClose(); }}>Done</button>
        : <><button onClick={onClose}>Cancel</button><button className="primary" onClick={make}>Make the key</button></>}>
      <div className="ed-form">
        {!out ? (
          <>
            <p className="quiet small">For the site that will send to this one. It is shown once; this site keeps only its fingerprint.</p>
            <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="From production" /></Field>
          </>
        ) : (
          <>
            <p>Give this key to the sending site's Super Admin. It is not shown again.</p>
            <p><code className="pairing-key">{out.key}</code></p>
            <button onClick={() => navigator.clipboard?.writeText(out.key)}>Copy</button>
          </>)}
        {err && <p className="status bad">{err}</p>}
      </div>
    </Modal>
  );
}

function Batches({ p, onChange }) {
  const [gen, setGen] = useState(0);
  const { data, error } = useApi(`/api/v1/pairings/${p.id}/batches?g=${gen}`);
  const [msg, setMsg] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading...</p>;
  const act = async (b, action) => {
    if (action === "discard" && !window.confirm(`Discard batch ${b.seq}? Its content is not taken; the next one may then be committed.`)) return;
    try { const r = await post(`/api/v1/sync-batches/${b.id}/${action}`); setMsg(r.message || r.status); setTimeout(() => { setGen((g) => g + 1); onChange(); }, 2500); }
    catch (e) { setMsg(e.message); }
  };
  return (
    <div className="pairing-batches">
      {msg && <p className="status ok small">{msg}</p>}
      {data.batches.length === 0 ? <p className="quiet small">No batches yet.</p> : (
        <table className="grid-table small">
          <thead><tr><th>#</th><th>State</th><th>Holds</th><th>Size</th><th>When</th><th>Answer and notes</th><th /></tr></thead>
          <tbody>{data.batches.map((b) => (
            <tr key={b.id}>
              <td>{b.seq}</td>
              <td>{BATCH[b.status] || b.status}{b.error && <div className="bad-text">{b.error}</div>}</td>
              <td>{(b.items || []).map((i) => i.name || i.id).join(", ")}</td>
              <td>{Math.max(1, Math.round((b.size || 0) / 1024))} KB</td>
              <td>{fmtDateTime(b.committed_at || b.sent_at || b.created_at)}</td>
              <td className="quiet">{b.reply ? `${b.reply.status || ""}${b.reply.site2 ? `, on the other site: ${b.reply.site2}` : ""}` : ""}
                {(b.notes || []).length > 0 && <ul>{b.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}</td>
              <td>{b.direction === "in" && ["waiting", "received", "failed"].includes(b.status) && (
                <><button onClick={() => act(b, "commit")}>Commit</button> <button onClick={() => act(b, "discard")}>Discard</button></>)}</td>
            </tr>))}</tbody>
        </table>)}
    </div>
  );
}

function Row({ p, refresh, setMsg }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState(p.commit_mode);
  const act = async (action, extra = {}) => {
    const sure = { stop: p.side === "receiver" && p.kind === "dr"
      ? "Stop the DR pairing and take over? This site stops being read only and people can work here. Failing back is pairing the other way."
      : "Stop this pairing? Nothing more is sent or taken until it is set up again.", remove: "Remove this pairing and its queue?" }[action];
    if (sure && !window.confirm(sure)) return;
    try {
      if (action === "remove") await apiFetch(`/api/v1/pairings/${p.id}`, { method: "DELETE" });
      else if (action === "send") { const r = await post(`/api/v1/pairings/${p.id}/send`); setMsg({ ok: true, text: r.message }); }
      else await post(`/api/v1/pairings/${p.id}`, { action, ...extra }, "PUT");
      refresh();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  };
  const b = p.batches || {};
  return (
    <>
      <tr>
        <td><b>{p.name}</b><div className="quiet small">{p.status === "key" ? "no site yet" : `${p.peer_name || "?"} · ${p.peer_url}`}</div></td>
        <td>{KIND[p.kind]}</td>
        <td>{STATUS[p.status] || p.status}{p.last_error && <div className="bad-text small">{p.last_error}</div>}</td>
        <td className="small">{p.side === "sender"
          ? (p.send_mode === "auto" ? `by itself, every ${p.every_minutes} min` : "by hand")
          : (p.commit_mode === "auto" ? "committed by itself" : "committed by a Super Admin")}
          <div className="quiet">{p.side === "sender" ? (p.scope?.all !== false ? "the entire site" : "chosen models and projects") : ""}</div></td>
        <td className="small">{p.lag}{Object.keys(b).length > 0 && <div className="quiet">{Object.entries(b).map(([k, n]) => `${n} ${BATCH[k] || k}`).join(", ")}</div>}</td>
        <td className="pairing-actions">
          {p.side === "sender" && p.status === "accepted" && <button className="primary" onClick={() => act("send")}>Sync now</button>}
          {p.side === "receiver" && p.status === "waiting" && (
            <>
              {p.kind === "content" && <select value={mode} onChange={(e) => setMode(e.target.value)}><option value="manual">Commit by hand</option><option value="auto">Commit by itself</option></select>}
              <button className="primary" onClick={() => act("accept", { commit_mode: mode })}>Accept</button>
              <button onClick={() => act("refuse")}>Refuse</button>
            </>)}
          {p.side === "receiver" && p.status === "accepted" && p.kind === "content" && (
            <button onClick={() => act("change", { commit_mode: p.commit_mode === "auto" ? "manual" : "auto" })}>
              {p.commit_mode === "auto" ? "Commit by hand" : "Commit by itself"}</button>)}
          {["waiting", "accepted"].includes(p.status) && <button onClick={() => act("stop")}>{p.side === "receiver" && p.kind === "dr" ? "Stop and take over" : "Stop"}</button>}
          {p.side === "sender" && p.status === "stopped" && <button onClick={() => act("resume")}>Resume</button>}
          <button onClick={() => setOpen(!open)}>{open ? "Hide batches" : "Batches"}</button>
          <button className="linkish" onClick={() => act("remove")}>Remove</button>
        </td>
      </tr>
      {open && <tr><td colSpan={6}><Batches p={p} onChange={refresh} /></td></tr>}
    </>
  );
}

export default function PairingsPage() {
  const [gen, setGen] = useState(0);
  const { data, error } = useApi(`/api/v1/pairings?g=${gen}`);
  const [dialog, setDialog] = useState("");
  const [msg, setMsg] = useState({ ok: true, text: "" });
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading...</p>;
  const refresh = () => setGen((g) => g + 1);
  const sending = data.pairings.filter((p) => p.side === "sender");
  const receiving = data.pairings.filter((p) => p.side === "receiver");
  const table = (rows) => (
    <table className="grid-table">
      <thead><tr><th>Pairing</th><th>Kind</th><th>State</th><th>How</th><th>Last</th><th /></tr></thead>
      <tbody>{rows.map((p) => <Row key={p.id} p={p} refresh={refresh} setMsg={setMsg} />)}</tbody>
    </table>
  );
  return (
    <div className="pairings-page">
      <p className="quiet">This site (<b>{data.local}</b>) is <b>{data.purpose}</b> (System settings › Site purpose: a label only). Sites are paired one way:
        the sending site's content goes over the other's, over HTTPS, in numbered batches each answered. Content sync carries models,
        projects and the organisation's content; DR sync adds the users and their roles (without their passwords: on the DR site people
        sign in through your directory, or set one with Forgot password) and keeps the other site read only.</p>
      {data.dr_copy && <p className="status warn">This site is a DR copy of <b>{data.dr_copy.from}</b>: read only. To work here (a failover),
        stop its DR pairing below. To fail back later, pair this site with the other one the other way.</p>}
      <div className="toolbar">
        <button className="primary" onClick={() => setDialog("pair")}>Pair with a site...</button>
        <button onClick={() => setDialog("key")}>Make a key...</button>
      </div>
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}
      <h3>Sending to</h3>
      {sending.length ? table(sending) : <p className="quiet">None: Pair with a site to send this site's content to another.</p>}
      <h3>Receiving from</h3>
      {receiving.length ? table(receiving) : <p className="quiet">None: Make a key for a site that will send here.</p>}
      {dialog === "pair" && <PairDialog onClose={() => setDialog("")} onDone={() => { setDialog(""); refresh(); }} />}
      {dialog === "key" && <KeyDialog onClose={() => setDialog("")} onDone={refresh} />}
    </div>
  );
}
