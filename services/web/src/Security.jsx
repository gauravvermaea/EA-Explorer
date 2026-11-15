// System admin > Security (Release 5): who may reach EA Explorer and how people sign in.
//   IP allow lists (R5.2, D686): a list per place, kept at the front door (nginx); an empty list lets everyone in; this
//     machine and EA Explorer's own containers are always allowed; a change that would shut you out is refused; the
//     addresses refused, most first. From the machine itself: eax allow clear.
//   Multi-factor sign-in (R5.3, D690): off (the default), admins, or everyone; who has a code set up; reset a device.
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";
import { fmtDateTime } from "./fmt";

export default function Security() {
  return (
    <div className="security-admin">
      <AllowLists />
      <Mfa />
    </div>
  );
}

function AllowLists() {
  const [data, setData] = useState(null);
  const [lists, setLists] = useState(null);
  const [trusted, setTrusted] = useState([]);
  const [refused, setRefused] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => {
    apiFetch("/api/v1/admin/allow").then((x) => { setData(x); setLists(x.lists); setTrusted(x.trusted || []); }).catch((e) => setErr(e.message));
    apiFetch("/api/v1/admin/allow/refused").then(setRefused).catch(() => {});
  };
  useEffect(() => { load(); }, []);
  if (!can("system.operate")) return <p className="quiet">The allow lists are seen by IT Admins, Auditors and Super Admins.</p>;
  if (err && !data) return <p className="status bad">{err}</p>;
  if (!data || !lists) return <p><span className="spinner" aria-hidden="true" /> Reading the allow lists…</p>;
  const may = data.may_change;
  const setEntry = (place, i, k, v) => setLists((l) => ({ ...l, [place]: l[place].map((e, j) => (j === i ? { ...e, [k]: v } : e)) }));
  const add = (place) => setLists((l) => ({ ...l, [place]: [...l[place], { address: "", name: "", why: "" }] }));
  const remove = (place, i) => setLists((l) => ({ ...l, [place]: l[place].filter((_e, j) => j !== i) }));
  async function save() {
    setBusy(true); setErr(""); setMsg("");
    try {
      const clean = Object.fromEntries(Object.entries(lists).map(([p, v]) => [p, v.filter((e) => e.address.trim())]));
      await apiFetch("/api/v1/admin/allow", { method: "PUT", body: JSON.stringify({ lists: clean, trusted: trusted.filter((e) => e.address.trim()) }) });
      setMsg("Saved: the front door takes the lists at once.");
      load();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }
  return (
    <section>
      <h2>Who may reach EA Explorer (IP allow lists)</h2>
      <p className="quiet">A list per place, kept at the front door. An empty list lets everyone in. This machine
        ({data.always?.join(", ")}) and EA Explorer&apos;s own containers ({data.internal?.join(", ") || "its Docker networks"}) are
        always allowed. Your address: <strong>{data.your_address || "unknown"}</strong>; a change that would shut you out is refused.
        If a list ever shuts everyone out, run <code>eax allow clear</code> on the machine itself.</p>
      {data.changed_at && <p className="small">Last changed {fmtDateTime(data.changed_at)} by {data.changed_by}.</p>}
      {Object.entries(data.places).map(([place, label]) => (
        <fieldset key={place} className="allow-place">
          <legend>{label} <span className="small">({lists[place].length ? `${lists[place].length} allowed` : "everyone"})</span></legend>
          <table className="grid-table">
            <thead><tr><th>Address or range</th><th>Name</th><th>Why</th><th /></tr></thead>
            <tbody>
              {lists[place].map((e, i) => (
                <tr key={i}>
                  <td><input aria-label="Address or range" value={e.address} disabled={!may} placeholder="10.1.0.0/16"
                    onChange={(ev) => setEntry(place, i, "address", ev.target.value)} /></td>
                  <td><input aria-label="Name" value={e.name} disabled={!may} onChange={(ev) => setEntry(place, i, "name", ev.target.value)} /></td>
                  <td><input aria-label="Why" value={e.why} disabled={!may} onChange={(ev) => setEntry(place, i, "why", ev.target.value)} /></td>
                  <td>{may && <button className="linkish" onClick={() => remove(place, i)}>Remove</button>}</td>
                </tr>))}
            </tbody>
          </table>
          {may && <button onClick={() => add(place)}>Add an address</button>}
        </fieldset>))}
      <fieldset className="allow-place">
        <legend>Load balancers trusted to say who the caller is</legend>
        <p className="small">Only when EA Explorer sits behind a load balancer: its address here, and the address it forwards is used.</p>
        {trusted.map((e, i) => (
          <div key={i}><input aria-label="Load balancer address" value={e.address} disabled={!may}
            onChange={(ev) => setTrusted((t) => t.map((x, j) => (j === i ? { ...x, address: ev.target.value } : x)))} />
            {may && <button className="linkish" onClick={() => setTrusted((t) => t.filter((_x, j) => j !== i))}>Remove</button>}</div>))}
        {may && <button onClick={() => setTrusted((t) => [...t, { address: "" }])}>Add a load balancer</button>}
      </fieldset>
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
      {may ? <button className="primary" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save the lists"}</button>
        : <p className="quiet">Only a Super Admin changes the lists.</p>}
      <h3>Refused</h3>
      {!refused ? <p className="quiet">Reading the refusals…</p> : refused.count === 0 ? <p className="quiet">No address has been refused since the front door started.</p> : (
        <>
          <p>{refused.count} refused: {Object.entries(refused.by_place).map(([p, n]) => `${p} ${n}`).join(", ")}.</p>
          <table className="grid-table"><thead><tr><th>Address</th><th>Times</th></tr></thead>
            <tbody>{refused.by_address.map(([a, n]) => <tr key={a}><td>{a}</td><td>{n}</td></tr>)}</tbody></table>
        </>)}
    </section>
  );
}

function Mfa() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [who, setWho] = useState("");
  const load = () => apiFetch("/api/v1/admin/security/mfa").then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (!can("system.operate")) return null;
  if (!d) return err ? <p className="status bad">{err}</p> : <p><span className="spinner" aria-hidden="true" /> Reading multi-factor sign-in…</p>;
  async function setMode(mode) {
    setErr(""); setMsg("");
    try {
      const r = await apiFetch("/api/v1/admin/settings", { method: "PUT", body: JSON.stringify({ mfa_mode: mode }) });
      setMsg(r.note || "Saved."); load();
    } catch (e) { setErr(e.message); }
  }
  async function reset() {
    setErr(""); setMsg("");
    try { const r = await apiFetch("/api/v1/admin/security/mfa/reset", { method: "POST", body: JSON.stringify({ username: who }) });
      setMsg(`${r.username}: ${r.removed} authenticator removed; they set up a new one at their next sign-in.`); setWho(""); load(); }
    catch (e) { setErr(e.message); }
  }
  const words = { off: "Off: nobody is asked (anyone may add an authenticator app to their own account)",
    admins: `Admins: ${d.admin_roles.join(", ")} set up a code at their next sign-in`, everyone: "Everyone sets up a code at their next sign-in" };
  return (
    <section>
      <h2>Multi-factor sign-in</h2>
      <p className="quiet">Codes from an authenticator app (TOTP), asked by Keycloak after the password. Off unless you turn it on.</p>
      {d.modes.map((m) => (
        <label key={m} className="radio-row"><input type="radio" name="mfa" checked={d.mode === m} disabled={!d.may_change}
          onChange={() => setMode(m)} /> {words[m]}</label>))}
      {d.error ? <p className="status warn">{d.error}</p>
        : <p>{d.with_code.length} of {d.people} people have a code set up{d.asked.length ? `; ${d.asked.length} asked to set one up` : ""}.</p>}
      {d.may_change && (
        <p><label>Reset the authenticator of (lost phone): <input value={who} onChange={(e) => setWho(e.target.value)} /></label>
          {" "}<button disabled={!who.trim()} onClick={reset}>Reset</button></p>)}
      {err && <p className="status bad" role="alert">{err}</p>}
      {msg && <p className="status ok">{msg}</p>}
    </section>
  );
}
