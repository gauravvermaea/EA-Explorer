// System Admin › Footprint (R2.22; owner, 13 Nov 2026: "measure only for now"): how much each container takes, the newest
// measurement beside the one before (image, own disk, volumes, memory, CPU, seconds to start). The same as `eax footprint`.
// Memory over time (R3.5-M1): the newest watch (`eax footprint --watch`, or a self-test run, which is always watched):
// each container's lowest, average and peak, the whole installation's peak beside the guide (10 GB, not a limit) and
// whether the Docker host paged.
// The resource history (R3.5-M8; owner, 14 Nov 2026: "instrument memory CPU disk cache etc every 15 min configurable from
// admin screen and have it available and can be deleted ... while testing or working and keeping it"): a sample every
// few minutes, kept; charted over a period, the interval set here, CSV, deleted by a Super Admin. Helpers: resourceChart.js.
import { useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { useApi } from "./ModelViews";
import { Modal } from "./ModelOps";
import { fmtDateTime } from "./fmt";
import { CHARTS, EVERY, PERIODS, containerTable, deleteChoice, lines, periodQuery } from "./resourceChart";

const COLS = [["image_mb", "Image MB"], ["own_disk_mb", "Own disk MB"], ["volumes_mb", "Volumes MB"], ["memory_mb", "Memory MB"],
  ["cpu_percent", "CPU %"], ["start_seconds", "Start s"]];

export default function FootprintPage() {
  const [tick, setTick] = useState(0);
  const { data, error } = useApi(`/api/v1/admin/footprint?t=${tick}`);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function measure() {
    setBusy(true); setErr("");
    try { await apiFetch("/api/v1/admin/footprint", { method: "POST", body: JSON.stringify({ label }) }); setTick((t) => t + 1); }
    catch (e) { setErr(e.message); }
    setBusy(false);
  }
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading...</p>;
  const m = data.latest;
  const was = Object.fromEntries(((data.before || {}).containers || []).map((r) => [r.container, r]));
  const cell = (r, k) => {
    const v = r[k]; const b = (was[r.container] || {})[k];
    if (v === null || v === undefined) return "-";
    return typeof b === "number" && b !== v ? <>{v} <span className="quiet small">({v - b > 0 ? "+" : ""}{(v - b).toFixed(1)})</span></> : v;
  };
  return (
    <div>
      <p className="quiet">How much each container takes. Measure before and after a change: the change since the measurement before
        is in brackets. The same on the command line: <code>eax footprint [label]</code> (kept in work/footprint).</p>
      <div className="row-gap">
        <input placeholder="Label (optional)" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Label" />
        <button className="primary" onClick={measure} disabled={busy}>{busy ? "Measuring..." : "Measure now"}</button>
      </div>
      {err && <p className="status bad">{err}</p>}
      {!m ? <p className="quiet">Nothing measured yet.</p> : (
        <>
          <p className="small">{fmtDateTime(m.at)}{m.label && ` (${m.label})`}{data.before && <> · compared with {fmtDateTime(data.before.at)}</>}</p>
          <table className="grid-table">
            <thead><tr><th>Container</th>{COLS.map(([k, l]) => <th key={k}>{l}</th>)}<th>Restarts</th></tr></thead>
            <tbody>{(m.containers || []).map((r) => (
              <tr key={r.container}><td>{r.container}</td>{COLS.map(([k]) => <td key={k}>{cell(r, k)}</td>)}<td>{r.restarts || 0}</td></tr>))}
              <tr><td><b>All</b></td><td>{m.totals.image_mb}</td><td>{m.totals.own_disk_mb}</td><td>{m.totals.volumes_mb}</td><td>{m.totals.memory_mb}</td><td /><td /><td /></tr>
            </tbody>
          </table>
          {m.problems && m.problems.length > 0 && <p className="quiet small">Not measured: {m.problems.join("; ")}</p>}
        </>)}
      <ResourceHistory />
      <MemoryWatch w={data.memory} />
    </div>
  );
}

const gb = (mb) => `${(mb / 1024).toFixed(1)} GB`;

// The newest memory watch (R3.5-M1): a self-test run is always watched; `eax footprint --watch [minutes] [label]` too.
function MemoryWatch({ w }) {
  return (
    <div className="merge-step">
      <h3>Memory over time</h3>
      {!w ? <p className="quiet">Not watched yet: every self-test run is watched on its own, or run <code>eax footprint --watch 30 at-rest</code>.</p> : <>
        <p className="small">{fmtDateTime(w.at)} to {fmtDateTime(w.until)}{w.label && ` (${w.label})`} · {w.minutes} minutes, {w.samples} samples</p>
        <p><b>Peak of the whole installation: {gb(w.total_peak_mb)}</b> at {fmtDateTime(w.total_peak_at)}, average {gb(w.total_average_mb)}
          {" "}<span className={w.within_target ? "status ok" : "status warn"}>{w.within_target ? "within" : "above"} the guide of {gb(w.target_mb)}</span>
          {" "}<span className="quiet small">(a guide, not a limit)</span></p>
        {w.host && w.host.total_mb && <p className="small">Docker host {gb(w.host.total_mb)}; the least left at any moment {gb(w.host.least_available_mb)};
          swap in use at most {Math.round(w.host.most_swap_used_mb)} MB (at the start {Math.round(w.host.swap_used_at_start_mb)} MB):{" "}
          <b className={w.host.paged ? "status bad" : "status ok"}>{w.host.paged ? "it paged" : "no paging"}</b></p>}
        <table className="grid-table">
          <thead><tr><th>Container</th><th>Lowest MB</th><th>Average MB</th><th>Peak MB</th><th>Peak at</th></tr></thead>
          <tbody>{(w.containers || []).map((r) => <tr key={r.container}><td>{r.container}</td><td>{r.lowest_mb}</td><td>{r.average_mb}</td>
            <td>{r.peak_mb}</td><td>{fmtDateTime(r.peak_at)}</td></tr>)}</tbody>
        </table>
      </>}
    </div>
  );
}

// ---------------------------------------------------------------- the resource history (R3.5-M8)
function Chart({ points, fields, unit, top, title }) {
  if (!points.length) return null;
  const { paths, bands, top: yTop } = lines(points, fields, { top });
  return (
    <figure className="res-chart">
      <figcaption><b>{title}</b> <span className="quiet small">({unit}, top {yTop}{unit === "%" ? "%" : ""})</span>
        {paths.map((p, i) => <span key={p.field} className={`res-key res-line-${i}`}> {p.label}</span>)}</figcaption>
      <svg viewBox="0 0 720 140" preserveAspectRatio="none" role="img" aria-label={`${title} over the period`}>
        {bands.map((b, i) => <rect key={i} x={b.x0} y="0" width={Math.max(1, b.x1 - b.x0)} height="140" className="res-band"><title>{b.what}</title></rect>)}
        {paths.map((p, i) => <path key={p.field} d={p.d} className={`res-line res-line-${i}`} fill="none" vectorEffect="non-scaling-stroke" />)}
      </svg>
    </figure>
  );
}

function ResourceHistory() {
  const [period, setPeriod] = useState("1d");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [tick, setTick] = useState(0);
  const [shown, setShown] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [del, setDel] = useState(null);
  const [draft, setDraft] = useState(null);
  const q = periodQuery(period, from, to);
  const { data, error } = useApi(`/api/v1/admin/resources?${q}&t=${tick}`);
  if (error) return <div className="merge-step"><h3>Resource history</h3><p className="status bad">{error}</p></div>;
  if (!data) return <div className="merge-step"><h3>Resource history</h3><p>Loading...</p></div>;
  const s = data.settings;
  const d = draft || { every_minutes: s.every_minutes, detail_days: s.detail_days, keep_days: s.keep_days, boost_every: 1, boost_hours: 2 };
  const sum = data.summary || {};
  const table = containerTable(data.containers);
  const one = shown && data.containers[shown];
  async function call(fn, done) {
    setBusy(true); setErr(""); setMsg("");
    try { const out = await fn(); setMsg(done(out)); setTick((t) => t + 1); }
    catch (e) { setErr(e.message); }
    setBusy(false);
  }
  const put = (body) => call(() => apiFetch("/api/v1/admin/resources/settings", { method: "PUT", body: JSON.stringify(body) }),
    () => { setDraft(null); return "Saved: it applies from the next minute."; });
  return (
    <div className="merge-step">
      <h3>Resource history</h3>
      <p className="quiet">Memory, CPU, disk and the database's cache of every container, sampled all the time, while people work and
        while the self-test runs, and kept. The shaded stretches are a self-test, a backup, a restore or a start-up. On the
        command line: <code>eax footprint --history [days]</code>.</p>
      <div className="res-settings ed-form">
        <label>A sample every <select value={d.every_minutes} onChange={(e) => setDraft({ ...d, every_minutes: Number(e.target.value) })}>
          {[...new Set([...EVERY, s.every_minutes])].sort((a, b) => a - b).map((m) => <option key={m} value={m}>{m === 0 ? "off" : `${m} minute${m === 1 ? "" : "s"}`}</option>)}</select></label>
        <label>every sample kept <input type="number" min="1" max="365" value={d.detail_days} onChange={(e) => setDraft({ ...d, detail_days: e.target.value })} /> days, then one an hour</label>
        <label>kept <input type="number" min="1" max="3650" value={d.keep_days} onChange={(e) => setDraft({ ...d, keep_days: e.target.value })} /> days</label>
        <button disabled={busy || !draft} onClick={() => put({ every_minutes: d.every_minutes, detail_days: Number(d.detail_days), keep_days: Number(d.keep_days) })}>Save</button>
      </div>
      <div className="res-settings">
        {s.boost ? <>
          <span className="status warn">For now a sample every {s.boost.every} minute{s.boost.every === 1 ? "" : "s"}, until {fmtDateTime(s.boost.until)}</span>
          <button disabled={busy} onClick={() => put({ boost_every: 0 })}>Back to every {s.every_minutes} minutes now</button>
        </> : <>
          <span>For a while (a test):</span>
          <label>every <select value={d.boost_every} onChange={(e) => setDraft({ ...d, boost_every: Number(e.target.value) })}>
            {[1, 2, 5].map((m) => <option key={m} value={m}>{m} minute{m === 1 ? "" : "s"}</option>)}</select></label>
          <label>for <select value={d.boost_hours} onChange={(e) => setDraft({ ...d, boost_hours: Number(e.target.value) })}>
            {[1, 2, 4, 8, 12, 24].map((h) => <option key={h} value={h}>{h} hour{h === 1 ? "" : "s"}</option>)}</select></label>
          <button disabled={busy} onClick={() => put({ boost_every: d.boost_every, boost_hours: d.boost_hours })}>Start</button>
        </>}
        <span className="quiet small">{s.now_every_minutes ? `Last sample ${data.last_sample ? fmtDateTime(data.last_sample) : "not yet"}.` : "Off: no samples are taken."}</span>
      </div>
      <div className="toolbar">
        {PERIODS.map(([k, label]) => <button key={k} className={period === k ? "primary" : ""} onClick={() => setPeriod(k)}>{label}</button>)}
        <button className={period === "custom" ? "primary" : ""} onClick={() => setPeriod("custom")}>From ... to</button>
        {period === "custom" && <><input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From" />
          <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To" /></>}
        <button disabled={busy} onClick={() => call(() => apiFetch("/api/v1/admin/resources/sample", { method: "POST" }), () => "Sampled now.")}>Sample now</button>
        <button disabled={busy} onClick={() => call(() => apiDownload(`/api/v1/admin/resources/csv?${q}`, "resources.csv"), () => "Downloaded.")}>⬇ CSV</button>
        {data.may_delete && <button className="danger" disabled={busy} onClick={() => setDel({ kind: "period", before: "" })}>Delete...</button>}
      </div>
      {msg && <p className="status ok">{msg}</p>}
      {err && <p className="status bad">{err}</p>}
      {!data.points.length ? <p className="quiet">Nothing kept from {fmtDateTime(data.from)} to {fmtDateTime(data.to)}.
        {s.now_every_minutes ? ` The first sample comes within ${s.now_every_minutes} minutes, or press Sample now.` : " Choose an interval above to start."}</p> : <>
        <p className="small">{fmtDateTime(data.from)} to {fmtDateTime(data.to)} · {sum.samples} samples ·
          memory peak <b>{gb(sum.memory_peak_mb)}</b> at {fmtDateTime(sum.memory_peak_at)}, average {gb(sum.memory_average_mb)} ·
          CPU peak {sum.cpu_peak_percent}% · least left on the host {sum.least_available_mb == null ? "-" : gb(sum.least_available_mb)} ·{" "}
          <b className={sum.paged ? "status bad" : "status ok"}>{sum.paged ? "it paged" : "no paging"}</b>
          {sum.activity && sum.activity.length > 0 && <> · during {sum.activity.join(", ")}</>}</p>
        <div className="res-charts">
          {CHARTS.map(([k, title, fields, unit, top]) => <Chart key={k} points={data.points} fields={fields} unit={unit} top={top} title={title} />)}
          {one && <Chart points={one} fields={[["memory_peak_mb", "peak"], ["memory_mb", "average"]]} unit="MB" title={`Memory: ${shown}`} />}
          {one && <Chart points={one} fields={[["cpu_percent", "CPU"]]} unit="%" top={100} title={`CPU: ${shown}`} />}
        </div>
        <table className="grid-table">
          <thead><tr><th>Container</th><th>Average MB</th><th>Peak MB</th><th>CPU % peak</th><th /></tr></thead>
          <tbody>{table.map((r) => <tr key={r.name} className={shown === r.name ? "changed-here" : ""}><td>{r.name}</td><td>{r.average ?? "-"}</td>
            <td>{r.peak}</td><td>{r.cpuPeak}</td><td><button className="linkish" onClick={() => setShown(shown === r.name ? "" : r.name)}>{shown === r.name ? "Hide" : "Chart"}</button></td></tr>)}</tbody>
        </table>
        {data.disks.length > 0 && <p className="small">{data.disks.map((x) => `${x.label}: ${x.used_gb} of ${x.total_gb} GB used (${x.used_percent}%)`).join(" · ")}</p>}
      </>}
      {del && <DeleteHistory data={data} del={del} setDel={setDel} done={(m) => { setDel(null); setMsg(m); setTick((t) => t + 1); }} />}
    </div>
  );
}

function DeleteHistory({ data, del, setDel, done }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const choice = deleteChoice(del.kind, data, del.before);
  async function go() {
    setBusy(true); setErr("");
    try { const out = await apiFetch(`/api/v1/admin/resources${choice[0] ? "?" + choice[0] : ""}`, { method: "DELETE" }); done(out.message); }
    catch (e) { setErr(e.message); setBusy(false); }
  }
  return (
    <Modal title="Delete resource history" onClose={() => setDel(null)}
      actions={<><button className="danger" disabled={busy || !choice} onClick={go}>{busy ? "Deleting..." : "Delete"}</button>
        <button onClick={() => setDel(null)}>Cancel</button></>}>
      <div className="ed-radio">
        <label><input type="radio" checked={del.kind === "period"} onChange={() => setDel({ ...del, kind: "period" })} /> The period shown
          ({fmtDateTime(data.from)} to {fmtDateTime(data.to)})</label>
        <label><input type="radio" checked={del.kind === "before"} onChange={() => setDel({ ...del, kind: "before" })} /> Everything before{" "}
          <input type="datetime-local" value={del.before} onChange={(e) => setDel({ ...del, kind: "before", before: e.target.value })} aria-label="Before" /></label>
        <label><input type="radio" checked={del.kind === "all"} onChange={() => setDel({ ...del, kind: "all" })} /> All of it</label>
      </div>
      <p>{choice ? <>This deletes <b>{choice[1]}</b> for good. It is recorded in the audit log.</> : "Choose the date first."}</p>
      {err && <p className="status bad">{err}</p>}
    </Modal>
  );
}
