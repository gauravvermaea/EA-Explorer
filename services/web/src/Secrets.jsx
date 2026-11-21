// System Admin › Secrets (R6-S1, D743; owner, 17 Nov 2026, 18:47: "in the admin tab we need a secrets tab to keep us
// updated"). Every password, key and certificate by name, never a value: how it is changed (by itself, or by a person),
// when it last changed, when it is next due, and what needs a person and by when. Rotate now (one, or every one that
// is due) runs eax secrets rotate in the Command centre's runner: the database or Keycloak is changed too, and the
// services that use it are made again (a few seconds each). The certificate authority itself is never changed here:
// eax certs on the machine (D743).
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "./auth";
import { useApi } from "./ModelViews";
import FrontCertificate from "./FrontCert";

const KIND = {
  database: "a database login: changed in the database too",
  keycloak: "a sign-in client's secret: changed in Keycloak too",
  here: "used only by EA Explorer's own services",
  person: "needs a person",
};

// The rotation followed here, on this page (the owner, 18 Nov 2026, 09:41: "can we either show status here itself or
// update when done. I cant even find the command page"): its output as it comes, then done or failed, and the table
// read again. The API itself may be made again during a rotation: the page keeps asking until it answers.
// after Rotate all, the page offers the restart (the owner, 18 Nov 2026, 09:56: "If done form web app, it asks for
// restart of the app"): through the Command centre; where it cannot run from the web (Windows), the command to type
function RestartOffer() {
  const [said, setSaid] = useState("");
  const restart = async () => {
    if (!window.confirm("Restart EA Explorer now? Everyone is signed out for a few minutes while it starts again.")) return;
    try {
      await apiFetch("/api/v1/admin/commands/run", { method: "POST", body: JSON.stringify({ argv: ["restart"] }) });
      setSaid("Restarting: this page comes back when EA Explorer is up again (a few minutes).");
    } catch (e) { setSaid(e.message); }
  };
  return (
    <div className="status warn" role="status">
      <p><b>Restart EA Explorer now?</b> Every service then starts with the new values. Recommended after Rotate all.</p>
      <button className="primary" onClick={restart}>Restart EA Explorer</button>
      {said && <p className="small">{said}</p>}
    </div>
  );
}

function RotationRun({ run, onDone }) {
  const [text, setText] = useState("");
  const [state, setState] = useState("running");
  const [away, setAway] = useState(false);
  const pos = useRef(0);
  useEffect(() => {
    let live = true;
    let timer;
    let misses = 0;
    const tick = async () => {
      try {
        const d = await apiFetch(`/api/v1/admin/commands/runs/${run.id}?from=${pos.current}`);
        if (!live) return;
        misses = 0;
        setAway(false);
        if (d.text) { pos.current = d.next; setText((x) => x + d.text); }
        const s = d.status?.state || "running";
        if (s === "running" || d.running) { timer = setTimeout(tick, 2000); return; }
        setState(s);
        onDone(s);
      } catch {
        if (!live) return;
        misses += 1;
        if (misses > 2) setAway(true);           // EA Explorer's services being made again with the new values
        timer = setTimeout(tick, 3000);
      }
    };
    void tick();
    return () => { live = false; clearTimeout(timer); };
  }, [run.id]);  // eslint-disable-line react-hooks/exhaustive-deps
  const lines = text.split("\n").filter((l) => l.trim() && !l.startsWith("$ ") && !l.startsWith("[finished"));
  const ok = state === "done" || state === "ok" || state === "succeeded";
  return (
    <div className={`status ${state === "running" ? "" : ok ? "ok" : "bad"}`} role="status" aria-live="polite">
      {state === "running"
        ? <p><span className="spinner" aria-hidden="true" /> Rotating {run.what}...{away
          ? " EA Explorer is making its services again with the new values: this page carries on when it answers." : ""}</p>
        : <p><b>{ok ? "Done" : "It did not finish"}</b>: {run.what}. {ok ? "The table below shows the new ages."
          : "The new values are saved; run eax restart on the machine to make the services again, then rotate again if needed."}</p>}
      {lines.length > 0 && <pre className="small secrets-run">{lines.slice(-15).join("\n")}</pre>}
      <p className="quiet small">Its full record: <a href="#/admin/commands/history">System Admin › Command centre › History</a>.</p>
      {run.all && state !== "running" && ok && <RestartOffer />}
    </div>
  );
}

// Rotate all on a schedule (D763; the owner, 18 Nov 2026, 10:11: "Restart now or Restart at 5 PM on xyz date and then
// there is a regular schedule like you said monthly or every 90 days"): the Command centre's schedules, as in Jenkins
const ALL_ARGV = "secrets rotate --all";
function RotateAllSchedule() {
  const [list, setList] = useState(null);
  const [at, setAt] = useState("");
  const [said, setSaid] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => apiFetch("/api/v1/admin/commands/schedules").then((r) => setList((r.schedules || [])
    .filter((s) => (s.argv || []).join(" ") === ALL_ARGV))).catch((e) => setSaid(e.message));
  useEffect(() => { void load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (argv) => {
    setBusy(true); setSaid("");
    try {
      const r = await apiFetch("/api/v1/admin/commands/run", { method: "POST", body: JSON.stringify({ argv }) });
      for (let i = 0; i < 60; i += 1) {
        await new Promise((ok) => setTimeout(ok, 1500));
        const d = await apiFetch(`/api/v1/admin/commands/runs/${r.id}`).catch(() => null);
        const s = d?.status?.state;
        if (s && s !== "running" && !d.running) {
          setSaid(s === "done" ? "Saved." : (d.text || "").split("\n").filter((l) => l.trim()).slice(-2).join(" "));
          break;
        }
      }
    } catch (e) { setSaid(e.message); }
    setBusy(false);
    void load();
  };
  const regular = (list || []).find((s) => s.id === "r6rotateall" && s.enabled);
  const once = (list || []).filter((s) => s.once_at && s.next);
  return (
    <div className="rotate-schedule">
      <h3>Rotate all on a schedule</h3>
      <p className="quiet small">Behind the maintenance page, once the background has finished; the same schedules as Jenkins
        (System Admin › Command centre › Schedules), so nothing runs twice.</p>
      <p>Regularly: <b>{regular ? `${regular.when}; next ${String(regular.next || "").replace("T", " ")}` : "off"}</b>{" "}
        <select disabled={busy} value="" onChange={(e) => e.target.value && run(["secrets", "schedule", e.target.value])}>
          <option value="">Change...</option>
          <option value="monthly">Monthly (1st, 03:30)</option>
          <option value="quarterly">Every three months (about 90 days)</option>
          <option value="off">Off</option>
        </select></p>
      <p>Once, at: <input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />{" "}
        <button disabled={busy || !at} onClick={() => run(["secrets", "schedule", "--at", at.slice(0, 16)])}>Schedule it</button></p>
      {once.length > 0 && <ul className="small">{once.map((s) => <li key={s.id}>{String(s.next).replace("T", " ")}{" "}
        <a href="#/admin/commands/schedules">(cancel it on Schedules)</a></li>)}</ul>}
      {said && <p className="small">{said}</p>}
    </div>
  );
}

function Due({ s }) {
  if (s.due) return <span className="bad-text">due now</span>;
  if (s.warn) return <span className="warn-text">in {s.days_left} days</span>;
  return <span className="quiet">{s.due_at || "-"}</span>;
}

export default function SecretsPage() {
  const [gen, setGen] = useState(0);
  const { data, error } = useApi(`/api/v1/admin/secrets?g=${gen}`);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [run, setRun] = useState(null);
  const [busy, setBusy] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading...</p>;
  const secrets = data.secrets || [];
  const certs = data.certificates || [];
  const person = secrets.filter((s) => !s.auto && (s.due || s.warn));
  const rotate = async (key) => {
    const what = key === "--due" ? "every password and key that is due"
      : key === "--all" ? "EVERY password and key EA Explorer can rotate (what needs a person is left alone)" : key;
    const after = key === "--all" ? " The maintenance page goes up and the background is let finish first; the services are made again at the end, then you are asked to restart EA Explorer."
      : " The services that use it are made again: a few seconds each.";
    if (!window.confirm(`Rotate ${what} now?${after} Only one rotation runs at a time.`)) return;
    setBusy(key);
    setMsg({ ok: true, text: "" });
    try {
      // the confirm above already said the maintenance page goes up for Rotate all: its yes goes with it
      const r = await apiFetch("/api/v1/admin/secrets/rotate", { method: "POST", body: JSON.stringify({ key, accept_maintenance: key === "--all" }) });
      setRun({ id: r.run, all: key === "--all",
        what: key === "--all" ? "every password and key (behind the maintenance page)" : key === "--due" ? "every one that is due" : key });
    } catch (e) { setMsg({ ok: false, text: e.message }); setBusy(""); }
  };
  const finished = () => { setBusy(""); setGen((g) => g + 1); };
  return (
    <div className="secrets-page">
      <p className="quiet">Every password, key and certificate EA Explorer uses, by name: their values are never shown. The services
        sign in with <b>{data.mode === "certificate" ? "certificates" : "passwords"}</b> (EAX_AUTH_MODE). Passwords and keys
        rotate by themselves every <b>{data.days} days</b>{data.laptop && !data.rotate_on_laptop
          ? " on a server (this laptop keeps its own unless EAX_ROTATE_ON_LAPTOP=on)" : ""}; certificates renew by themselves.
        What needs a person is alerted at 30, 14 and 7 days (System Admin › Alerts).</p>
      {person.length > 0 && (
        <div className="status warn" role="status">
          <b>Needs a person:</b>
          <ul>{person.map((s) => <li key={s.key}><code>{s.key}</code> {s.due ? "is due now" : `in ${s.days_left} days`}: {s.why}</li>)}</ul>
        </div>)}
      <div className="toolbar">
        <button className="primary" disabled={!!busy} onClick={() => rotate("--due")}>Rotate every one that is due now</button>{" "}
        <button disabled={!!busy} onClick={() => rotate("--all")}>Rotate all</button>
      </div>
      {run && <RotationRun key={run.id} run={run} onDone={finished} />}
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}
      <h3>Passwords and keys</h3>
      <table className="grid-table">
        <thead><tr><th>Setting</th><th>How it changes</th><th>Last changed</th><th>Next due</th><th /></tr></thead>
        <tbody>{secrets.map((s) => (
          <tr key={s.key}>
            <td><code className="small">{s.key}</code>{!s.set && <span className="quiet small"> (not set)</span>}</td>
            <td className="small">{s.auto ? "by itself" : "by a person"}<span className="quiet">: {KIND[s.kind] || s.kind}</span>
              {s.why && <div className="quiet small">{s.why}</div>}</td>
            <td className="small">{s.changed ? `${s.changed.slice(0, 10)}${s.how ? ` (${s.how}${s.by ? `, ${s.by}` : ""})` : ""}` : "-"}</td>
            <td className="small"><Due s={s} /></td>
            <td>{s.auto && s.set && <button disabled={!!busy} onClick={() => rotate(s.key)}>Rotate now</button>}</td>
          </tr>))}</tbody>
      </table>
      <RotateAllSchedule />
      <FrontCertificate />
      <h3>Certificates</h3>
      {certs.length === 0 ? <p className="quiet">None: the services sign in with passwords. eax init --certificate, or eax certs switch,
        moves an installation to certificates (R6-C1).</p> : (
        <table className="grid-table">
          <thead><tr><th>Certificate</th><th>Issued by</th><th>Valid until</th><th>Renews</th><th /></tr></thead>
          <tbody>{certs.map((c) => (
            <tr key={c.name}>
              <td><b>{c.name}</b> <span className="quiet small">{c.what}</span></td>
              <td className="small">{c.issuer}</td>
              <td className="small"><Due s={c} /> <span className="quiet">{c.not_after}</span></td>
              <td className="small">{c.auto ? "by itself" : "by a person"}</td>
              <td>{c.auto && <button disabled={!!busy} onClick={() => rotate(`cert:${c.name}`)}>Renew now</button>}</td>
            </tr>))}</tbody>
        </table>)}
    </div>
  );
}
