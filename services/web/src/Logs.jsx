// System admin > Logs (R5.6, R5.7; D688: our own page, no extra tool): every log in one place.
//   Container logs  every container's log, a file a day (R2.31, R2.32), by level (debug to critical), time and words
//   Web log         every call to the API and MCP (when, who, from where, method and path, status, how long, bytes,
//                   request id), filtered, slowest first, the slowest and most failing routes summed; CSV and zip
//   Web log debug   off by default; on for a while (each call's input and answer too, masked), said here while on
//   eax's own logs  work/logs and the log backups
//   Size and keeping how large each log file grows before a new one starts (100 KB by default), the same for Docker's
//                   own copy of each container's output (from the next eax up), and the days kept (R5.26)
//   Delete          a period, everything before a day, or all (Super Admin; a log backup first). Logs older than
//                   7 days go by themselves every night; clean-run and clean-restart delete them after a backup.
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";
import { KeptLogs, OwnLogs } from "./ContainerConsole";
import { fmtDateTime } from "./fmt";

const TABS = [["containers", "Container logs"], ["web", "Web log"], ["own", "eax's own logs"], ["rolling", "Size and keeping"], ["delete", "Delete logs"]];

export default function Logs() {
  const [tab, setTab] = useState("containers");
  return (
    <div className="logs-admin">
      <p className="quiet">Every log in one place. Each file rolls over at 100 KB and is kept for 7 days unless changed under Size and
        keeping; levels from debug to critical, info by default.</p>
      <div className="row-gap small-tabs" role="tablist" aria-label="Which logs">
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "containers" && <KeptLogs service="api" />}
      {tab === "web" && <WebLog />}
      {tab === "own" && <OwnLogs />}
      {tab === "rolling" && <Rolling />}
      {tab === "delete" && <DeleteLogs />}
    </div>
  );
}

// Size and keeping (R5.26): every log file rolls over at a size (a new file begins, the full one is compressed); Docker's
// own copy of each container's output too, from the next eax up; the days every file is kept, however many there are.
function Rolling() {
  const [d, setD] = useState(null);
  const [f, setF] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const may = can("settings.manage");
  const load = () => apiFetch("/api/v1/admin/logs/rolling").then((x) => { setD(x); setF({ file_kb: x.file_kb, docker_kb: x.docker_kb, keep_days: x.keep_days }); })
    .catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (!d) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading…</p>;
  async function save(e) {
    e.preventDefault();
    setBusy(true); setErr(""); setMsg("");
    try {
      const x = await apiFetch("/api/v1/admin/logs/rolling", { method: "PUT", body: JSON.stringify({ file_kb: Number(f.file_kb), docker_kb: Number(f.docker_kb), keep_days: Number(f.keep_days) }) });
      setD(x);
      setMsg(x.docker_kb_running != null && x.docker_kb_running !== x.docker_kb
        ? "Saved. The log files roll at the new size from now; Docker's copy takes its new size at the next .\\eax up."
        : "Saved and applied.");
    } catch (x) { setErr(x.message); }
    setBusy(false);
  }
  const field = (k, label, help, min, max) => (
    <p><label>{label}<br /><input type="number" min={min} max={max} value={f[k]} disabled={!may}
      onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label><br /><span className="small quiet">{help}</span></p>);
  return (
    <form className="logs-rolling" onSubmit={save}>
      <p className="quiet">Each log file grows to its size, then a new one begins and the full one is compressed. Every file is
        kept for the days below, however many files that is, then deleted in the night.</p>
      {field("file_kb", "Log files roll over at (KB)", "The containers' logs, the web log and its debug lines. 100 KB by default; from 10 KB to 1 GB (1048576).", 10, 1048576)}
      {field("docker_kb", "Docker's own copy rolls over at (KB)", `Docker keeps each container's output until it is copied here every minute (5 files a container). 100 KB by default; taken at the next .\\eax up${d.docker_kb_running != null ? ` (running now: ${d.docker_kb_running} KB)` : ""}.`, 10, 1048576)}
      {field("keep_days", "Kept for (days)", "Every log file and log backup older than this is deleted every night; 0 keeps them.", 0, 3650)}
      {d.set_by && <p className="small quiet">Last set by {d.set_by}{d.set_at ? ` on ${fmtDateTime(d.set_at)}` : ""}.</p>}
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {may ? <button className="primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button> : <p className="small quiet">Only a Super Admin changes these.</p>}
    </form>
  );
}

function saveText(name, text, type = "text/csv") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function saveBase64(name, b64) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function WebLog() {
  const [files, setFiles] = useState(null);
  const [f, setF] = useState({ day: "", since: "", until: "", who: "", path: "", status: "", sort: "time" });
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [minutes, setMinutes] = useState("60");
  const [note, setNote] = useState("");
  useEffect(() => { apiFetch("/api/v1/admin/logs/web/files").then((x) => setFiles(x.files || [])).catch((e) => setErr(e.message)); }, []);
  const days = [...new Set((files || []).map((x) => x.day))].sort().reverse();
  const day = f.day || days[0] || "";
  const query = (extra = {}) => new URLSearchParams({ ...f, day, page, ...extra }).toString();
  async function load() {
    if (!day) return;
    setErr("");
    try { setData(await apiFetch(`/api/v1/admin/logs/web?${query()}`)); } catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, [day, f.status, f.sort, page]);   // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k, v) => { setF((x) => ({ ...x, [k]: v })); setPage(0); };
  async function csv() {
    try { const r = await apiFetch(`/api/v1/admin/logs/web/csv?${query()}`); saveText(r.name, r.csv); } catch (e) { setErr(e.message); }
  }
  async function zip() {
    try { const r = await apiFetch(`/api/v1/admin/logs/web/zip?start=${day}&end=${day}`); saveBase64(r.name, r.zip); } catch (e) { setErr(e.message); }
  }
  async function debug(on) {
    setNote("");
    try {
      const r = await apiFetch("/api/v1/admin/logs/web-debug", { method: "POST", body: JSON.stringify({ minutes: on ? Number(minutes) : 0 }) });
      setNote(r.on ? `Web log debug is on until ${fmtDateTime(r.until)}.` : "Web log debug is off."); load();
    } catch (e) { setErr(e.message); }
  }
  if (files && !files.length) return <p className="quiet">No web log yet: the front door writes one line for every call to the API and MCP (logs/web).</p>;
  const s = data?.summary;
  return (
    <div>
      {data?.debug_until && <p className="status warn" role="status">Web log debug is on until {fmtDateTime(data.debug_until)}: each call&apos;s input and answer are written too (masked).</p>}
      <div className="row-gap filters">
        <select value={day} onChange={(e) => set("day", e.target.value)} aria-label="Day">{days.map((d) => <option key={d} value={d}>{d}</option>)}</select>
        <input type="time" value={f.since} onChange={(e) => set("since", e.target.value)} aria-label="Since" title="Since" />
        <input type="time" value={f.until} onChange={(e) => set("until", e.target.value)} aria-label="Until" title="Until" />
        <input type="search" placeholder="Person" value={f.who} onChange={(e) => set("who", e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
        <input type="search" placeholder="Path" value={f.path} onChange={(e) => set("path", e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
        <select value={f.status} onChange={(e) => set("status", e.target.value)} aria-label="Status">
          <option value="">Every status</option><option value="errors">Errors and refusals (4xx, 5xx)</option>
          <option value="5xx">Errors (5xx)</option><option value="4xx">Refused (4xx)</option>
        </select>
        <select value={f.sort} onChange={(e) => set("sort", e.target.value)} aria-label="Order">
          <option value="time">By time</option><option value="slowest">Slowest first</option>
        </select>
        <button onClick={load}>Show</button>
        <button onClick={csv} disabled={!data?.total}>Download CSV</button>
        <button onClick={zip}>Download the raw files</button>
      </div>
      {err && <p className="status bad">{err}</p>}
      {note && <p className="status ok">{note}</p>}
      {s && (
        <div className="row-gap">
          <div><strong>{s.calls}</strong> calls, <strong>{s.errors}</strong> errors</div>
          <table className="grid-table small"><caption>Slowest (95th percentile, seconds)</caption>
            <thead><tr><th>Route</th><th>Calls</th><th>Average</th><th>95%</th></tr></thead>
            <tbody>{s.slowest.map((r) => <tr key={r.route}><td>{r.route}</td><td>{r.calls}</td><td>{r.average}</td><td>{r.p95}</td></tr>)}</tbody></table>
          {s.failing.length > 0 && <table className="grid-table small"><caption>Most failing</caption>
            <thead><tr><th>Route</th><th>Errors</th><th>Calls</th></tr></thead>
            <tbody>{s.failing.map((r) => <tr key={r.route}><td>{r.route}</td><td>{r.errors}</td><td>{r.calls}</td></tr>)}</tbody></table>}
        </div>)}
      {data && (
        <>
          <p className="quiet small">{data.total} call(s){data.pages > 1 && <> · page {data.page + 1} of {data.pages}{" "}
            <button className="small" disabled={page === 0} onClick={() => setPage(page - 1)}>‹ Earlier</button>{" "}
            <button className="small" disabled={page >= data.pages - 1} onClick={() => setPage(page + 1)}>Later ›</button></>}</p>
          <table className="grid-table small">
            <thead><tr><th>When</th><th>Who</th><th>From</th><th>Call</th><th>Status</th><th>Seconds</th><th>Bytes</th><th>Request id</th></tr></thead>
            <tbody>{data.rows.map((r, i) => (
              <tr key={i} className={r.status >= 500 ? "bad" : r.status >= 400 ? "warn" : ""}>
                <td>{String(r.time).slice(11, 19)}</td><td>{r.who || "-"}</td><td>{r.address}</td><td>{r.method} {r.path}</td>
                <td>{r.status}</td><td>{r.seconds}</td><td>{r.bytes}</td><td className="small">{r.request_id}</td>
              </tr>))}</tbody>
          </table>
        </>)}
      {can("settings.manage") && (
        <fieldset>
          <legend>Web log debug</legend>
          <p className="small">Off by default. While on, each API call&apos;s input and answer are written too (cut to 4 KB, every password,
            secret, token, key and personal field masked), in logs/web/debug-&lt;day&gt;.log. It goes off by itself.</p>
          <label>For how many minutes <input type="number" min="1" max="1440" value={minutes} onChange={(e) => setMinutes(e.target.value)} /></label>
          {" "}<button onClick={() => debug(true)}>Switch on</button>{" "}<button onClick={() => debug(false)}>Switch off</button>
        </fieldset>)}
    </div>
  );
}

function DeleteLogs() {
  const [what, setWhat] = useState("before");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  if (!can("settings.manage")) return <p className="quiet">Only a Super Admin deletes logs by hand. Logs older than 7 days are deleted every night.</p>;
  async function go() {
    setErr(""); setNote("");
    const said = what === "all" ? "every log" : what === "before" ? `every log before ${start}` : `the logs from ${start} to ${end}`;
    if (!window.confirm(`Delete ${said}? A log backup is taken first; the deletion cannot be undone.`)) return;
    try {
      const r = await apiFetch("/api/v1/admin/logs/clean-range", { method: "POST", body: JSON.stringify({ what, start, end }) });
      setNote(`Deleted ${r.deleted.length} file(s); backed up first to ${r.backup}.`);
    } catch (e) { setErr(e.message); }
  }
  return (
    <div>
      <p className="quiet">The container logs and the web log. A log backup is taken first (it stays with the log backups).</p>
      <label className="radio-row"><input type="radio" checked={what === "before"} onChange={() => setWhat("before")} /> Everything before a day</label>
      <label className="radio-row"><input type="radio" checked={what === "period"} onChange={() => setWhat("period")} /> A period</label>
      <label className="radio-row"><input type="radio" checked={what === "all"} onChange={() => setWhat("all")} /> All of it</label>
      {what !== "all" && <label>From <input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>}
      {what === "period" && <label> to <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>}
      <p><button className="danger" disabled={what !== "all" && !start || what === "period" && !end} onClick={go}>Delete</button></p>
      {err && <p className="status bad" role="alert">{err}</p>}
      {note && <p className="status ok">{note}</p>}
    </div>
  );
}
