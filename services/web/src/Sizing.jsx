// System admin > Sizing (R5.19): the server sizing estimate. People at once, models and their size, projects and their
// documents, what is switched on: the answer is the server's RAM, CPU cores and disk, and per container the memory to
// reserve and its limit, the copies, the volumes, the settings, the nodes on a container platform and a compose override
// to paste. Always a best estimate (eax/sizing.py): it says so and shows the assumptions, which can be changed here; on a
// running installation the estimate for a laptop's figures is set beside what each container really used. Also eax estimate.
import { useEffect, useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { fmtDateTime } from "./fmt";

const FIELDS = [["users", "People at once"], ["models", "Models"], ["projects", "Projects"], ["documents_per_project", "Documents a project"],
  ["backups_kept", "Backups kept"], ["headroom", "Headroom (0.3 = 30%)"], ["node_gb", "Platform node: GB"], ["node_cores", "Platform node: cores"]];
const SWITCHES = [["reports", "Reports"], ["documents", "Documents"], ["mcp", "MCP server"], ["discovery", "Discovery"]];

export default function Sizing() {
  const [d, setD] = useState(null);
  const [f, setF] = useState(null);
  const [r, setR] = useState(null);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => apiFetch("/api/v1/admin/sizing").then((x) => {
    setD(x); setF((old) => old || { ...x.defaults, model_size: x.defaults.model_size, node_gb: 16, node_cores: 4, reports: true, documents: true,
      mcp: true, discovery: true, assumptions: { ...x.assumptions } });
  }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (!d || !f) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading…</p>;
  async function go(save) {
    setErr(""); setMsg("");
    try {
      const out = await apiFetch("/api/v1/admin/sizing", { method: "POST", body: JSON.stringify({ ...f, save: save ? name : "" }) });
      setR(out); if (save) { setMsg(`Saved as ${name}.`); load(); }
    } catch (e) { setErr(e.message); }
  }
  const set = (k, v) => setF({ ...f, [k]: v });
  const file = (id, fmt) => apiDownload(`/api/v1/admin/sizing/${id}/${fmt}`, `eaexplorer-sizing-${id}.${fmt === "override" ? "yml" : fmt}`).catch((e) => setErr(e.message));
  return (
    <div className="sizing">
      <p className="quiet">A best estimate of what a server needs, before it is made (model {d.model_version}; no server-class machine has measured it
        yet): change the figures and the assumptions to fit, and check it against what the installation really uses. On the command
        line: <code>eax estimate --users 50 --models 30 --projects 40</code>.</p>
      <div className="form-grid">
        {FIELDS.map(([k, l]) => <label key={k}>{l} <input type="number" value={f[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></label>)}
        <label>Model size <select value={f.model_size} onChange={(e) => set("model_size", e.target.value)}>
          <option value="small">small (500 elements)</option><option value="medium">medium (5,000)</option><option value="large">large (25,000)</option></select></label>
        {SWITCHES.map(([k, l]) => <label key={k} className="check"><input type="checkbox" checked={!!f[k]} onChange={(e) => set(k, e.target.checked)} /> {l}</label>)}
      </div>
      <details><summary>Assumptions</summary>
        <div className="form-grid">{Object.entries(f.assumptions).map(([k, v]) => (
          <label key={k}>{k.replace(/_/g, " ")} <input type="number" step="any" value={v}
            onChange={(e) => setF({ ...f, assumptions: { ...f.assumptions, [k]: e.target.value } })} /></label>))}</div>
      </details>
      <div className="row-gap">
        <button className="primary" onClick={() => go(false)}>Estimate</button>
        <input placeholder="Name to save it under" value={name} onChange={(e) => setName(e.target.value)} />
        <button onClick={() => go(true)} disabled={!name.trim()}>Estimate and save</button>
      </div>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {r && (
        <div className="sizing-result">
          <p className="status warn">{r.says}</p>
          <h3>{r.server.ram_gb} GB RAM · {r.server.cores} CPU cores · {r.server.disk_gb} GB disk</h3>
          <p className="small">Needed {r.server.ram_needed_gb} GB, {r.server.cores_needed} cores and {r.server.disk_needed_gb} GB with {Math.round(r.headroom * 100)}%
            headroom, rounded to sizes servers come in. On a container platform: {r.platform.nodes} nodes of {r.platform.node_gb} GB and {r.platform.node_cores} cores (one spare).</p>
          {r.split.length > 0 && <p className="status warn">Past one server's size: {r.split.join("; ")}.</p>}
          <table className="grid-table small">
            <thead><tr><th>Container</th><th>What</th><th>Copies</th><th>Reserve MB</th><th>Limit MB</th><th>CPU</th><th>CPU limit</th></tr></thead>
            <tbody>{r.containers.map((c) => <tr key={c.container}><td>{c.container}</td><td>{c.what}</td><td>{c.copies}{c.many ? "" : " (one only)"}</td>
              <td>{c.memory_reserve_mb}</td><td>{c.memory_limit_mb}</td><td>{c.cpu_reserve}</td><td>{c.cpu_limit}</td></tr>)}</tbody>
          </table>
          <p className="small">Disk now and in a year (GB): {Object.entries(r.disk).map(([k, v]) => `${k} ${v} / ${r.disk_in_a_year[k]}`).join(" · ")}</p>
          <p className="small">Settings: {Object.entries(r.settings).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
          <details><summary>Compose override</summary><pre className="code-block">{r.override}</pre></details>
        </div>)}
      {d.measured.some((m) => m.really_mb != null) && (
        <>
          <h3>A laptop's estimate beside what this installation really used (the last 7 days' peaks)</h3>
          <table className="grid-table small">
            <thead><tr><th>Container</th><th>Estimate MB</th><th>Limit MB</th><th>Really used MB</th></tr></thead>
            <tbody>{d.measured.map((m) => <tr key={m.container}><td>{m.container}</td><td>{m.estimate_mb}</td><td>{m.limit_mb}</td>
              <td className={m.really_mb > m.limit_mb ? "bad" : ""}>{m.really_mb ?? "-"}</td></tr>)}</tbody>
          </table>
        </>)}
      <h3>Saved</h3>
      {!d.saved.length ? <p>None yet.</p> : (
        <table className="grid-table small">
          <thead><tr><th>Name</th><th>When</th><th>By</th><th>Server</th><th /></tr></thead>
          <tbody>{d.saved.map((s) => <tr key={s.id}><td>{s.name}</td><td>{fmtDateTime(s.at)}</td><td>{s.by_whom}</td>
            <td>{s.server ? `${s.server.ram_gb} GB, ${s.server.cores} cores, ${s.server.disk_gb} GB` : ""}</td>
            <td><button className="small" onClick={() => file(s.id, "xlsx")}>Excel</button>{" "}
              <button className="small" onClick={() => file(s.id, "override")}>Compose override</button></td></tr>)}</tbody>
        </table>)}
    </div>
  );
}
