// System Admin > Running > Jobs (R5.30; owner, 15 Nov 2026: "a jobs view which clearly shows what is in job queue";
// "Jobs in queue how many are worked on, abilty to kill, move things down in priority. User friendly description";
// "if a job is stuck for too long I should see in the dashboard number of jobs stuck and advise to clear them or delete
// them from queue or add more api servers"; "I will not run commands I want a UI").
//   JobsSummary  the counts, big: being worked on, waiting, stuck, the free job slots; what to do (on the dashboard too)
//   Jobs         every job being worked on and waiting, in words, with Kill, Cancel, Move down and up; the newest finished
//   Priorities   each kind of job's level (high, normal, low), changeable, and how often a low one missed its turn (R5.6-Q2)
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";
import { fmtDateTime } from "./fmt";

const mins = (m) => (m == null ? "" : m < 1 ? "under a minute" : m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1)} h`);

function useQueue(every = 5000) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const load = () => apiFetch("/api/v1/jobs/queue").then((x) => { setD(x); setErr(""); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); const t = setInterval(load, every); return () => clearInterval(t); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  return [d, err, load];
}

export function JobsSummary({ link = true }) {
  const [d, err] = useQueue(15000);
  if (!can("system.operate")) return null;
  if (err) return <p className="status bad small">Jobs: {err}</p>;
  if (!d) return null;
  const s = d.summary;
  return (
    <section className={`jobs-summary${s.stuck ? " stuck" : ""}`} aria-live="polite">
      <div className="jobs-kpis">
        <div className="jobs-kpi"><b>{s.running}</b><span>being worked on</span></div>
        <div className="jobs-kpi"><b>{s.waiting}</b><span>waiting</span></div>
        <div className={`jobs-kpi${s.stuck ? " bad" : ""}`}><b>{s.stuck}</b><span>stuck</span></div>
        <div className="jobs-kpi"><b>{s.free_slots}</b><span>of {s.slots} slots free</span></div>
      </div>
      {s.stuck > 0 && <ul className="jobs-advice">{s.advice.map((a, i) => <li key={i}>{a.text}</li>)}</ul>}
      {s.stuck_running > 0 && <ClearStuck />}
      {link && <p className="small"><a href="#/admin/jobs">{s.stuck ? "See and clear the stuck jobs ›" : "The job queue ›"}</a></p>}
    </section>
  );
}

// One button for the alert's advice (owner, 21:46: "an alert to kill and clear the job queue"): every stuck job being
// worked on killed, then the job runner restarted so their work ends and the waiting ones start.
function ClearStuck() {
  const [ask, setAsk] = useState(false);
  const [msg, setMsg] = useState("");
  async function go() {
    try {
      const r = await apiFetch("/api/v1/jobs/queue/clear-stuck", { method: "POST", body: JSON.stringify({ restart: true }) });
      setMsg(`${r.killed.length} stuck job(s) killed; the job runner is restarting: the screens come back within a minute.`);
    } catch (e) { setMsg("The job runner is restarting: the screens come back within a minute."); }
    setAsk(false);
  }
  return (
    <p className="toolbar">
      {!ask ? <button className="primary danger" onClick={() => setAsk(true)}>Clear the stuck jobs</button>
        : <><span>Kill every stuck job and restart the job runner (the screens are back within a minute)?</span>
          <button className="primary danger" onClick={go}>Yes, clear them</button><button onClick={() => setAsk(false)}>No</button></>}
      {msg && <span className="status ok"> {msg}</span>}
    </p>
  );
}

// Deleting the finished jobs' history (R5.34; owner, 15 Nov 2026: "add ability to delete job history"): all, or those
// that ended more than some days ago; waiting and running jobs are never touched. Asked first.
function DeleteHistory({ onDone }) {
  const [days, setDays] = useState(7);
  const [ask, setAsk] = useState(false);
  const [msg, setMsg] = useState("");
  async function go() {
    setAsk(false);
    try {
      const r = await apiFetch(`/api/v1/jobs/queue/history?older_than_days=${Number(days) || 0}`, { method: "DELETE" });
      setMsg(`${r.deleted} finished job(s) deleted from the history.`); onDone();
    } catch (e) { setMsg(e.message); }
  }
  return (
    <p className="toolbar small">
      <label>Delete the finished jobs that ended more than <input type="number" min="0" value={days} style={{ width: 64 }}
        onChange={(e) => setDays(e.target.value)} /> days ago (0: all of them)</label>
      {!ask ? <button onClick={() => setAsk(true)}>Delete job history</button>
        : <><span>{Number(days) ? `Delete every finished job older than ${days} days` : "Delete every finished job"}? Waiting and running jobs stay.</span>
          <button className="primary danger" onClick={go}>Yes, delete</button><button onClick={() => setAsk(false)}>No</button></>}
      {msg && <span className="status ok"> {msg}</span>}
    </p>
  );
}

// Each API server's job slots (R5.33; owner, 15 Nov 2026: "give me ability to increase or decrease job slots with
// warnings if they are more than number of available threads. This should be where I can add or remove api containers
// and in the auto scaling"): on Scaling, Containers and Jobs. Saved in the settings; the API servers take them when they
// restart (Apply now).
export function JobSlots({ compact = false }) {
  const [d, setD] = useState(null);
  const [f, setF] = useState(null);
  const [msg, setMsg] = useState("");
  const [bad, setBad] = useState("");
  const [asked, setAsked] = useState(false);
  const load = () => apiFetch("/api/v1/jobs/slots").then((x) => { setD(x); setF((o) => o || { tasks: x.per_server.tasks, scheduled: x.per_server.scheduled }); })
    .catch((e) => setBad(e.message));
  useEffect(() => { load(); }, []);
  if (!can("system.operate")) return null;
  if (!d || !f) return bad ? <p className="status bad small">{bad}</p> : null;
  const per = Number(f.tasks || 0) + Number(f.scheduled || 0) + 1;
  const web = 2;
  const now = (per + web) * d.servers, most = (per + web) * d.most_servers;
  const over = d.threads && now > d.threads, overMost = d.auto && d.threads && most > d.threads;
  const changed = Number(f.tasks) !== d.per_server.tasks || Number(f.scheduled) !== d.per_server.scheduled;
  async function save() {
    setMsg(""); setBad("");
    try {
      const x = await apiFetch("/api/v1/jobs/slots", { method: "PUT", body: JSON.stringify({ tasks: Number(f.tasks), scheduled: Number(f.scheduled) }) });
      setD(x); setMsg(x.message);
    } catch (e) { setBad(e.message); }
  }
  async function apply() {
    setAsked(false);
    try { await apiFetch("/api/v1/jobs/queue/restart-runner", { method: "POST" }); } catch (e) { /* the restart takes the API with it */ }
    setMsg("The API servers are restarting with the new job slots: the screens come back within a minute.");
  }
  const num = (k, label, max) => (
    <label className="job-slot">{label}<br />
      <span className="row-gap">
        <button type="button" aria-label={`Fewer: ${label}`} onClick={() => setF({ ...f, [k]: Math.max(1, Number(f[k]) - 1) })}>−</button>
        <input type="number" min="1" max={max} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
        <button type="button" aria-label={`More: ${label}`} onClick={() => setF({ ...f, [k]: Math.min(max, Number(f[k]) + 1) })}>+</button>
      </span></label>);
  return (
    <section className={`q-card job-slots${over || overMost ? " warn" : ""}`}>
      <h3>Job slots on each API server</h3>
      {!compact && <p className="quiet small">How many background jobs each API server works on at once: people's work (backups,
        deliveries, merges) and the scheduled jobs, each with slots of their own, and one for the alert checks. More slots
        finish a long queue sooner but share the same CPUs; each API server adds its own.</p>}
      <div className="row-gap">
        {num("tasks", "People's work", 32)}
        {num("scheduled", "Scheduled jobs", 16)}
        <span className="small quiet">+ 1 for the alerts</span>
      </div>
      <p className="small">Each server: <b>{per}</b> job slots and {web} web workers · {d.servers} server(s) now: <b>{now}</b> at once
        {d.auto ? <> · up to {d.most_servers} servers by the scaling rules: <b>{most}</b></> : null}
        {d.threads ? <> · this machine has <b>{d.threads}</b> CPU threads</> : <> · the CPU threads could not be read</>}</p>
      {over && <p className="status warn small">{now} at once is more than the {d.threads} CPU threads: jobs and screens will slow
        each other down. Fewer slots, fewer servers, or a machine with more CPUs.</p>}
      {!over && overMost && <p className="status warn small">When the scaling rules reach {d.most_servers} servers, {most} at once is
        more than the {d.threads} CPU threads: fewer slots, or a lower "Most servers".</p>}
      <div className="toolbar">
        <button className="primary" disabled={!changed} onClick={save}>Save</button>
        {!changed &&
          (!asked ? <button onClick={() => setAsked(true)}>Apply now (restart the API servers)</button>
            : <><span className="small">Restart the API servers now? Jobs being worked on stop; the screens are back within a minute.</span>
              <button className="primary" onClick={apply}>Yes, restart</button><button onClick={() => setAsked(false)}>No</button></>)}
      </div>
      {msg && <p className="status ok small">{msg}</p>}
      {bad && <p className="status bad small" role="alert">{bad}</p>}
    </section>
  );
}

export default function Jobs() {
  const [d, err, load] = useQueue(5000);
  const [msg, setMsg] = useState("");
  const [bad, setBad] = useState("");
  const [ask, setAsk] = useState(null);
  async function act(job, action) {
    setMsg(""); setBad("");
    try {
      const r = await apiFetch(`/api/v1/jobs/queue/${job.id}/${action}`, { method: "POST" });
      setMsg(action === "kill" ? `${job.what}: ${r?.message || "asked to stop."}`
        : action === "cancel" ? `${job.what}: taken off the queue.` : `${job.what}: moved ${action}.`);
      if (r) load();
    } catch (e) { setBad(e.message); }
    setAsk(null);
  }
  async function restart() {
    setMsg(""); setBad("");
    try {
      const r = await apiFetch("/api/v1/jobs/queue/restart-runner", { method: "POST" });
      setMsg(r.message || "The job runner is restarting.");
    } catch (e) { setMsg("The job runner is restarting: the screens come back within a minute."); }
    setAsk(null);
  }
  if (err && !d) return <p className="status bad">{err}</p>;
  if (!d) return <p><span className="spinner" aria-hidden="true" /> Reading the job queue…</p>;
  const working = d.jobs.filter((j) => j.status !== "todo"), waiting = d.jobs.filter((j) => j.status === "todo");
  return (
    <div className="jobs-page">
      <p className="quiet">Background work (backups, deliveries, reports, checks) waits here for one of the job runner's slots,
        then is worked on. A job is <b>stuck</b> when it has waited more than {d.limits[0]} minutes or been worked on more than
        {" "}{d.limits[1]} minutes (three times that for backups, restores and tests). The page refreshes every 5 seconds.</p>
      <JobsSummary link={false} />
      <JobSlots compact />
      {msg && <p className="status ok">{msg}</p>}
      {bad && <p className="status bad" role="alert">{bad}</p>}
      <div className="toolbar">
        <button onClick={() => setAsk({ restart: true })}>Restart the job runner</button>
        <a className="button-link" href="#/admin/scaling">Add API servers (more job slots) ›</a>
      </div>

      <h2>Being worked on ({working.length})</h2>
      {!working.length ? <p className="quiet">Nothing right now.</p> : (
        <table className="grid-table jobs-table">
          <thead><tr><th>What</th><th>Asked by</th><th>Started</th><th>For</th><th /></tr></thead>
          <tbody>{working.map((j) => (
            <tr key={j.id} className={j.stuck ? "stuck" : ""}>
              <td><b>{j.what}</b><br /><span className="small quiet">job {j.id}{j.label ? ` · ${j.task_name.replace("eax.", "")}` : ""}</span>
                {j.stuck && <><br /><span className="status bad small">Stuck: {j.why}</span></>}
                {!j.stuck && j.why && <><br /><span className="quiet small">{j.why}</span></>}</td>
              <td>{j.who}</td><td>{j.started_at ? fmtDateTime(j.started_at) : "-"}</td><td>{mins(j.minutes)}</td>
              <td><button className={j.stuck ? "danger" : ""} onClick={() => setAsk({ job: j, action: "kill" })}>
                {j.status === "aborting" ? "Mark stopped" : "Kill"}</button></td>
            </tr>))}</tbody>
        </table>)}

      <h2>Waiting, in the order they will start ({waiting.length})</h2>
      {!waiting.length ? <p className="quiet">Nothing is waiting.</p> : (
        <table className="grid-table jobs-table">
          <thead><tr><th>#</th><th>What</th><th>Asked by</th><th>Waiting</th><th /></tr></thead>
          <tbody>{waiting.map((j, i) => (
            <tr key={j.id} className={j.stuck ? "stuck" : ""}>
              <td>{i + 1}</td>
              <td><b>{j.what}</b><br /><span className="small quiet">job {j.id}{j.periodic ? " · on a schedule" : ""}</span>
                {j.stuck && <><br /><span className="status bad small">Stuck: {j.why}</span></>}
                {!j.stuck && j.why && <><br /><span className="quiet small">{j.why}</span></>}</td>
              <td>{j.who}</td><td>{mins(j.minutes)}</td>
              <td className="row-gap">
                <button disabled={i === 0} onClick={() => act(j, "up")} title="Start it before the others">Move up</button>
                <button disabled={i === waiting.length - 1} onClick={() => act(j, "down")} title="Start it after the others">Move down</button>
                <button onClick={() => setAsk({ job: j, action: "cancel" })}>Cancel</button>
              </td>
            </tr>))}</tbody>
        </table>)}

      <Priorities />

      <h2>Finished lately</h2>
      <DeleteHistory onDone={load} />
      {!d.finished.length ? <p className="quiet">None yet.</p> : (
        <table className="grid-table small jobs-table">
          <thead><tr><th>What</th><th>Asked by</th><th>How it ended</th><th>When</th></tr></thead>
          <tbody>{d.finished.map((j) => (
            <tr key={j.id}><td>{j.what}</td><td>{j.who}</td>
              <td className={j.status === "failed" || j.status === "aborted" ? "bad-text" : ""}>{j.status_words}</td>
              <td>{j.ended_at ? fmtDateTime(j.ended_at) : ""}</td></tr>))}</tbody>
        </table>)}

      {ask && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            {ask.restart ? (<>
              <h3>Restart the job runner?</h3>
              <p>The API restarts with it: every job being worked on stops, the waiting ones start, and the screens are back
                within a minute. Nothing waiting is lost.</p>
              <div className="toolbar"><button className="primary" onClick={restart}>Restart it</button><button onClick={() => setAsk(null)}>No</button></div>
            </>) : ask.action === "kill" ? (<>
              <h3>{ask.job.status === "aborting" ? `Mark “${ask.job.what}” stopped?` : `Kill “${ask.job.what}”?`}</h3>
              {ask.job.status === "aborting"
                ? <p>It was already asked to stop. Marking it stopped frees its slot and lets its next run start at once;
                  whoever asked for it sees it failed. Do this only when no job runner is still working on it (for example a
                  server that has gone); otherwise Restart the job runner (the button at the top) ends it properly.</p>
                : <p>It is asked to stop and shows as "Being stopped". A job already running can only really end when the
                  job runner restarts: Restart the job runner afterwards (the button at the top); the restart marks it
                  stopped and its next run starts.</p>}
              <div className="toolbar"><button className="primary danger" onClick={() => act(ask.job, "kill")}>Kill it</button><button onClick={() => setAsk(null)}>No</button></div>
            </>) : (<>
              <h3>Cancel “{ask.job.what}”?</h3>
              <p>It is taken off the queue and never starts; whoever asked for it sees it cancelled. A scheduled one comes
                back at its next time.</p>
              <div className="toolbar"><button className="primary" onClick={() => act(ask.job, "cancel")}>Cancel it</button><button onClick={() => setAsk(null)}>No</button></div>
            </>)}
          </div>
        </div>)}
    </div>
  );
}

// Each kind of job's level and its skips (R5.6-Q2; owner, 15 Nov 2026, 22:47; agreed 16 Nov 2026, 15:46)
function Priorities() {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState(null);
  const [open, setOpen] = useState(false);
  const load = () => apiFetch("/api/v1/jobs/priorities").then(setD).catch((e) => setMsg({ ok: false, text: e.message }));
  useEffect(() => { if (open && !d) load(); }, [open]);   // eslint-disable-line react-hooks/exhaustive-deps
  const may = can("system.operate");
  async function setLevel(k, level) {
    try { const r = await apiFetch(`/api/v1/jobs/priorities/${encodeURIComponent(k.task)}`, { method: "PUT", body: JSON.stringify({ level }) });
      setMsg({ ok: true, text: r.message }); load(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  const skipped = (d?.kinds || []).filter((k) => k.skipped_total);
  return (
    <>
      <h2><button className="linkish" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "▾" : "▸"} Priorities</button></h2>
      {open && (!d ? <p className="quiet">Loading...</p> : (<>
        <p className="small quiet">The job runner takes the highest first. When the queue is too full (more than {d.limits.jobs_full_waiting} waiting,
          or the oldest waiting over {d.limits.jobs_full_minutes} minutes), a waiting low-priority recurring job misses its turn and its next run
          does the work; after {d.limits.jobs_skip_max} skips in a row it runs anyway. A job someone asked for is never skipped. The limits are in
          System Admin › Settings.</p>
        {msg && <p className={`status ${msg.ok ? "ok" : "bad"}`}>{msg.text}</p>}
        {skipped.length > 0 && <p className="status">Skipped as the queue was too full: {skipped.map((k) => `${k.what} (${k.skipped_total})`).join(", ")}.</p>}
        <table className="grid-table small jobs-table">
          <thead><tr><th>Kind of job</th><th>Priority</th><th>Skipped</th><th>Last skipped</th></tr></thead>
          <tbody>{d.kinds.map((k) => (
            <tr key={k.task}>
              <td>{k.what}<div className="quiet small">{k.task}</div></td>
              <td><select value={k.level} disabled={!may} aria-label={`Priority of ${k.what}`} onChange={(e) => setLevel(k, e.target.value === k.default ? "" : e.target.value)}>
                {d.levels.map((l) => <option key={l} value={l}>{l}{l === k.default ? " (as it ships)" : ""}</option>)}</select></td>
              <td>{k.skipped_total ? `${k.skipped_total} (${k.skipped_in_row} in a row)` : "–"}</td>
              <td>{k.last_skipped ? fmtDateTime(k.last_skipped) : "–"}</td>
            </tr>))}</tbody>
        </table>
      </>))}
    </>
  );
}
