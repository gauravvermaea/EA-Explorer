// The upkeep an admin chooses (the owner, 18 Nov 2026, 10:21: "ensure its not restarting like this when it feels. The
// user needs to be able to enable the key rotation and all these schedules as one of the initial configuration tasks"):
// what can put the maintenance page up for a few minutes is off until chosen here. Shown in the first-run setup and on
// System Admin > Command centre > Schedules. Rotation and certificate renewal are off until chosen (18 Nov 2026, 10:58).
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";

async function runAndWait(argv) {
  const r = await apiFetch("/api/v1/admin/commands/run", { method: "POST", body: JSON.stringify({ argv }) });
  for (let i = 0; i < 60; i += 1) {
    await new Promise((ok) => setTimeout(ok, 1500));
    const d = await apiFetch(`/api/v1/admin/commands/runs/${r.id}`).catch(() => null);
    const s = d?.status?.state;
    if (s && s !== "running" && !d.running) return s === "done";
  }
  return false;
}

// Clean-up (D825; owner, 21 Nov 2026, 13:30: "In the regular mantiance tab please add ability to clean up logs and all
// these test result files etc"): now, older than the days given, and the test files every night when chosen above
export function CleanUp() {
  const [days, setDays] = useState({ logs: 14, files: 14, runs: 30 });
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const go = async (what, ask, url, body, said) => {
    if (!window.confirm(ask)) return;
    setBusy(what); setMsg("");
    try { const r = await apiFetch(url, { method: "POST", body: JSON.stringify(body) }); setMsg(said(r)); }
    catch (e) { setMsg(e.message); }
    setBusy("");
  };
  const n = (k) => Math.max(1, Number.parseInt(days[k], 10) || 1);
  const box = (k) => (<input type="number" min="1" max="3650" style={{ width: "5em" }} value={days[k]} disabled={!!busy}
    aria-label="days" onChange={(e) => setDays({ ...days, [k]: e.target.value })} />);
  return (
    <div className="upkeep-cleanup">
      <h4>Clean up now</h4>
      <ul className="upkeep-list">
        <li><b>Logs</b> older than {box("logs")} days{" "}
          <button disabled={!!busy} onClick={() => go("logs", `Delete the logs and log backups older than ${n("logs")} days, for good?`,
            "/api/v1/admin/logs/clean", { days: n("logs") }, (r) => `Logs: ${(r.deleted || []).length} file(s) deleted.`)}>Delete</button>
          <span className="quiet small"> the containers' logs, eax's own and the log backups; also every night after the days in
            System Admin › Settings "Delete logs older than"</span></li>
        <li><b>Test results' detailed files</b> older than {box("files")} days{" "}
          <button disabled={!!busy} onClick={() => go("files", `Delete the detailed test files older than ${n("files")} days? The summaries, counts and results stay.`,
            "/api/v1/admin/tests/prune", { older_than_days: n("files") }, (r) => r.message)}>Delete</button>
          <span className="quiet small"> reports, logs, videos, scanners' reports, screenshots, SonarQube and backup and restore
            results; the summaries stay (Self-test › Summary)</span></li>
        <li><b>Test runs</b> older than {box("runs")} days{" "}
          <button disabled={!!busy} onClick={() => go("runs", `Delete the test runs older than ${n("runs")} days FOR GOOD, their summaries too?`,
            "/api/v1/admin/tests/delete", { older_than_days: n("runs") }, (r) => r.message)}>Delete for good</button>
          <span className="quiet small"> everything of those runs, summaries included</span></li>
      </ul>
      {busy && <p className="small"><span className="spinner" aria-hidden="true" /> Deleting...</p>}
      {msg && <p className="small">{msg}</p>}
    </div>
  );
}

export default function UpkeepChoices({ cleanup = false }) {
  const [sch, setSch] = useState(null);
  const [fixes, setFixes] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => {
    apiFetch("/api/v1/admin/commands/schedules").then((r) => setSch(r.schedules || [])).catch((e) => setMsg(e.message));
    apiFetch("/api/v1/admin/settings").then((r) => setFixes(!!(r.system || []).find((s) => s.key === "integrity_fixes")?.value))
      .catch(() => {});
  };
  useEffect(() => { load(); }, []);
  if (!can("system.operate")) return null;
  if (!sch) return <p className="quiet">Reading the schedules...</p>;
  const due = sch.find((s) => s.id === "r6rotate");
  const certs = sch.find((s) => s.id === "r6certs");
  const tests = sch.find((s) => s.id === "r12tests");
  const all = sch.find((s) => s.id === "r6rotateall" && s.enabled);
  const act = async (what, fn) => {
    setBusy(what); setMsg("");
    try { await fn(); setMsg("Saved."); } catch (e) { setMsg(e.message); }
    setBusy(""); load();
  };
  return (
    <div className="upkeep-choices">
      <h3>Scheduled upkeep</h3>
      <p className="quiet small">Each of these can put the maintenance page up for a few minutes, so each is off until you choose it.</p>
      <ul className="upkeep-list">
        <li><label><input type="checkbox" disabled={!!busy || !due} checked={!!due?.enabled}
          onChange={(e) => act("due", () => apiFetch(`/api/v1/admin/commands/schedules/r6rotate/${e.target.checked ? "on" : "off"}`,
            { method: "POST", body: "{}" }))} /> <b>Rotate the passwords and keys that are due</b></label>
          <span className="quiet small"> every night at 03:17, each one every 90 days (System Admin › Secrets); a laptop keeps its own
            unless EAX_ROTATE_ON_LAPTOP=on</span></li>
        <li><b>Rotate all regularly</b>{" "}
          <select disabled={!!busy} value={all ? (all.cron === "30 3 1 * *" ? "monthly" : "quarterly") : "off"}
            onChange={(e) => act("all", async () => { if (!await runAndWait(["secrets", "schedule", e.target.value])) throw new Error("It did not save: see Command centre › History."); })}>
            <option value="off">Off</option>
            <option value="monthly">Monthly (the 1st, 03:30)</option>
            <option value="quarterly">Every three months (about 90 days)</option>
          </select>
          <span className="quiet small"> behind the maintenance page; once, at a time of your choosing: System Admin › Secrets</span></li>
        <li><label><input type="checkbox" disabled={!!busy || fixes === null} checked={!!fixes}
          onChange={(e) => act("fixes", () => apiFetch("/api/v1/admin/settings", { method: "PUT", body: JSON.stringify({ integrity_fixes: e.target.checked }) }))} />
          {" "}<b>Database safe fixes by themselves</b></label>
          <span className="quiet small"> after the weekly check (Sundays 02:20) and after a restore, with a backup first</span></li>
        <li><label><input type="checkbox" disabled={!!busy || !certs} checked={!!certs?.enabled}
          onChange={(e) => act("certs", () => apiFetch(`/api/v1/admin/commands/schedules/r6certs/${e.target.checked ? "on" : "off"}`,
            { method: "POST", body: "{}" }))} /> <b>Renew EA Explorer's own certificates when due</b></label>
          <span className="quiet small"> every night at 02:41 (certificate mode only: they last 30 days, so switch this on before
            using it, or renew by hand with eax certs renew)</span></li>
        {tests && <li><label><input type="checkbox" disabled={!!busy} checked={!!tests.enabled}
          onChange={(e) => act("tests", () => apiFetch(`/api/v1/admin/commands/schedules/r12tests/${e.target.checked ? "on" : "off"}`,
            { method: "POST", body: "{}" }))} /> <b>Delete the test results' detailed files older than 14 days</b></label>
          <span className="quiet small"> every night at 04:47; the summaries, counts and results stay (eax test prune)</span></li>}
      </ul>
      {cleanup && <CleanUp />}
      {busy && <p className="small"><span className="spinner" aria-hidden="true" /> Saving...</p>}
      {msg && <p className="small">{msg}</p>}
    </div>
  );
}
