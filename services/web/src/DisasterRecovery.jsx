// System admin › Disaster recovery (R5.6-B2; owner, 17 Nov 2026, 00:04: "On backup and restore page add a tab for DR and
// provide commands and steps for setup"). Steps and commands only: a DR pack, the drill and the rebuild run from the
// command line (they stop EA Explorer or run where it is not), never from here. The whole story with every option:
// Documentation › Disaster recovery: the DR pack and the DR tool (docs/backup-disaster-recovery.md), with its PDF.
import { useState } from "react";

const DOC = "#/documentation/backup-disaster-recovery";

// [Windows, Linux and macOS]
const CMD = {
  pack: [".\\eax dr-pack D:\\ea-dr-pack-2026-11-17", "./eax dr-pack /safe/ea-dr-pack-2026-11-17"],
  copy: ["robocopy D:\\ea-dr-pack-2026-11-17 \\\\newserver\\c$\\ea-dr-pack-2026-11-17 /E",
    "scp -r /safe/ea-dr-pack-2026-11-17 admin@newserver:/safe/"],
  rebuild: ["cd C:\\ea-dr-pack-2026-11-17\\dr\n.\\eax-dr.ps1 -Pack .. -Install C:\\EA-Explorer",
    "cd /safe/ea-dr-pack-2026-11-17/dr\n./eax-dr.sh --pack .. --install /opt/ea-explorer"],
  drill: [".\\dr\\eax-drill.ps1 -Install <this EA Explorer folder> -Dr C:\\EA-DR\\drill1 -Temp C:\\EA-DR\\temp",
    "./dr/eax-drill.sh --install <this EA Explorer folder> --dr /ea-dr/drill1 --temp /ea-dr/temp"],
  back: ["cd C:\\EA-DR\\drill1; .\\eax down\ncd <this EA Explorer folder>; .\\eax up",
    "cd /ea-dr/drill1 && ./eax down\ncd <this EA Explorer folder> && ./eax up"],
  test: [".\\eax test backup-restore", "./eax test backup-restore"],
};

function Cmd({ k, os }) {
  const [done, setDone] = useState(false);
  const text = CMD[k][os];
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); } catch { /* no clipboard: select it */ }
  };
  return (
    <div className="dr-cmd">
      <pre><code>{text}</code></pre>
      <button className="linkish small" onClick={copy}>{done ? "Copied" : "Copy"}</button>
    </div>
  );
}

const WHEN = [
  ["Someone deleted or spoilt content (a model, a project, documents)", "Restore a backup", "Backups tab, or eax restore <name>"],
  ["An upgrade or change went wrong, or the data is damaged, and the machine works", "Restore a backup", "eax restore <name>"],
  ["The machine is lost, broken or cannot be trusted", "DR", "eax-dr from a DR pack, on another machine"],
  ["The EA Explorer folder or Docker is gone or broken past repair", "DR", "eax-dr into a new folder"],
  ["EA Explorer moves to another server for good", "DR", "eax dr-pack here, eax-dr there"],
  ["You want proof a recovery works, and how long it takes", "The restore drill", "eax-drill, monthly and after each upgrade"],
];

export default function DisasterRecovery() {
  const [os, setOs] = useState(0);
  return (
    <div className="dr-page">
      <p className="quiet">When the machine EA Explorer runs on is lost, you build it again on another machine from a <b>DR pack</b>: a
        backup, the version, the config file and the code as it runs here (your own changes included), in one folder you keep away
        from this machine, with a checksum of every file and a fingerprint of all the data. The <b>DR tool</b> (<code>eax-dr</code>)
        rebuilds from it in one command, needs no GitHub, and proves the recovery by comparing every table and file. These run from the
        command line, not from this page: each asks nothing and writes a report. Every option and what to do when a step stops:{" "}
        <a href={DOC}>Disaster recovery: the DR pack and the DR tool</a> (with a PDF).</p>

      <div className="seg" role="tablist" aria-label="Commands for">
        {["Windows (PowerShell)", "Linux and macOS"].map((l, i) => (
          <button key={l} role="tab" aria-selected={os === i} className={os === i ? "on" : ""} onClick={() => setOs(i)}>{l}</button>))}
      </div>

      <h2>A backup or DR: which one</h2>
      <table className="dr-when">
        <thead><tr><th>What happened</th><th>Use</th><th>How</th></tr></thead>
        <tbody>{WHEN.map(([a, b, c]) => <tr key={a}><td>{a}</td><td><b>{b}</b></td><td>{c}</td></tr>)}</tbody>
      </table>
      <p className="small">A backup puts data back into an installation that still runs; DR builds the installation itself again, code and
        config included, where there is none.</p>

      <h2>Set it up: make a DR pack</h2>
      <ol className="dr-steps">
        <li>In this installation's folder, with EA Explorer running, make the pack in a new folder on a disk or share kept away from this
          machine. The maintenance page is on for a few minutes while the background finishes, the fingerprint and the backup are taken.
          <Cmd k="pack" os={os} />
          <span className="small">Check: it ends with <code>DR pack ready</code>. The pack holds <code>backup/</code>, <code>VERSION.txt</code>,{" "}
            <code>eaexplorer.env</code>, <code>code/</code>, <code>fingerprint.json</code>, <code>dr/</code>, <code>RESTORE.txt</code>{" "}
            and <code>PACK.sha256</code>.</span></li>
        <li>Keep it safe: the env file holds every password and key, the backup all the data. An encrypted disk, a locked share or your
          organisation's vault for backups; never only on this machine.</li>
        <li>Make a new pack after each upgrade, each change to the config file, and as often as you can afford to lose work.</li>
      </ol>

      <h2>Recover on another machine</h2>
      <ol className="dr-steps">
        <li>Get the machine ready: Docker running; access to Docker Hub and the Python and Node package sites (or your mirrors), not
          GitHub; free disk of three times the pack; ports 80 and 443 free; its name in DNS as the env file's <code>EAX_HOSTNAME</code>{" "}
          says (or give an edited copy of the env file with <code>{os ? "--env" : "-Env"}</code>).</li>
        <li>Copy the whole pack to it.
          <Cmd k="copy" os={os} /></li>
        <li>From the pack's <code>dr</code> folder, rebuild into a new or empty folder.
          <Cmd k="rebuild" os={os} />
          <span className="small">Check: it ends with <code>EA Explorer DR DONE</code>; the report (<code>&lt;install&gt;/work/dr/</code>)
            gives the comparison with the pack's fingerprint and the recovery time.</span></li>
        <li>Sign in with an account of the old installation, open a model, a project and one of its documents; then point your users at
          the new machine.</li>
      </ol>

      <h2>Rehearse it: the restore drill</h2>
      <ol className="dr-steps">
        <li>On this installation (its folder and data are not touched; the DR copy goes into a new folder under its own Docker name),
          give the installation, a new DR folder and a temp folder.
          <Cmd k="drill" os={os} />
          <span className="small">Check: it ends with <code>EA Explorer restore drill PASSED</code>.</span></li>
        <li>Go back to the installation (the DR copy is left running at the same address).
          <Cmd k="back" os={os} /></li>
        <li>Test the backups themselves too: the backup and restore test (about half an hour, the maintenance page on meanwhile).
          <Cmd k="test" os={os} /></li>
      </ol>
      <p className="quiet small">Not run from this page or by the Self-test: a pack, a rebuild or a drill stops EA Explorer or runs where it
        is not. Monthly: <a href="#/documentation/backup-drill-monthly">Restore drill: once a month</a>.</p>
    </div>
  );
}
