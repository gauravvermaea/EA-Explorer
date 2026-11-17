// System Admin › Secrets (R6-S1, D743; owner, 17 Nov 2026, 18:47: "in the admin tab we need a secrets tab to keep us
// updated"). Every password, key and certificate by name, never a value: how it is changed (by itself, or by a person),
// when it last changed, when it is next due, and what needs a person and by when. Rotate now (one, or every one that
// is due) runs eax secrets rotate in the Command centre's runner: the database or Keycloak is changed too, and the
// services that use it are made again (a few seconds each). The certificate authority itself is never changed here:
// eax certs on the machine (D743).
import { useState } from "react";
import { apiFetch } from "./auth";
import { useApi } from "./ModelViews";

const KIND = {
  database: "a database login: changed in the database too",
  keycloak: "a sign-in client's secret: changed in Keycloak too",
  here: "used only by EA Explorer's own services",
  person: "needs a person",
};

function Due({ s }) {
  if (s.due) return <span className="bad-text">due now</span>;
  if (s.warn) return <span className="warn-text">in {s.days_left} days</span>;
  return <span className="quiet">{s.due_at || "-"}</span>;
}

export default function SecretsPage() {
  const [gen, setGen] = useState(0);
  const { data, error } = useApi(`/api/v1/admin/secrets?g=${gen}`);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [busy, setBusy] = useState("");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p>Loading...</p>;
  const secrets = data.secrets || [];
  const certs = data.certificates || [];
  const person = secrets.filter((s) => !s.auto && (s.due || s.warn));
  const rotate = async (key) => {
    const what = key === "--due" ? "every password and key that is due" : key;
    if (!window.confirm(`Rotate ${what} now? The services that use it are made again: a few seconds each.`)) return;
    setBusy(key);
    try {
      const r = await apiFetch("/api/v1/admin/secrets/rotate", { method: "POST", body: JSON.stringify({ key }) });
      setMsg({ ok: true, text: `Started (run ${r.run}): follow it on System Admin › Commands. This page shows the new age when it is done.` });
      setTimeout(() => setGen((g) => g + 1), 4000);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy("");
  };
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
        <button className="primary" disabled={!!busy} onClick={() => rotate("--due")}>Rotate every one that is due now</button>
      </div>
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
