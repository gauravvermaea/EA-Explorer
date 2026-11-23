// People and roles (phase 3.1). Global roles are given in Keycloak (D92), never here: this page shows
// what each person's Keycloak roles give them in EA Explorer and their roles on models (given per model
// on each model's People tab, D96), and keeps the mapping from Keycloak roles to global roles.
import { useEffect, useMemo, useState } from "react";
import { apiFetch, can, roleName, needsRole } from "./auth";
import { downloadCsv } from "./exporting";
import { Modal } from "./ModelOps";

// R9.7 (owner, 21 Nov 2026: "force one user setup authenticator from user list if they lost phone or something"; D829)
const MFA_SHOWN = { "set up": "set up", asked: "asked to set up", none: "none" };

function MfaReset({ people, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const [error, setError] = useState("");
  async function go() {
    setBusy(true); setError("");
    try { setOut(await apiFetch("/api/v1/people/mfa-reset", { method: "POST", body: JSON.stringify({ usernames: people }) })); onDone(); }
    catch (err) { setError(err.message); }
    setBusy(false);
  }
  return (
    <Modal title="Set up the authenticator again" onClose={onClose}
      actions={out ? <button onClick={onClose}>Close</button>
        : <><button onClick={onClose}>Cancel</button><button className="primary" disabled={busy} onClick={go}>{busy ? "Asking..." : `Ask ${people.length === 1 ? "them" : `these ${people.length}`}`}</button></>}>
      {!out && <>
        <p>Ask <strong>{people.join(", ")}</strong> to set up their authenticator app again, now:</p>
        <ul>
          <li>the codes of their current authenticator stop working;</li>
          <li>they are signed out everywhere (the screens, Reports and Documents);</li>
          <li>their next sign-in shows a QR code to scan with their new phone, then asks for a code;</li>
          <li>they are emailed (when mail is set up), and it is recorded in the audit trail.</li>
        </ul>
        <p className="quiet">Their tokens, API keys and certificates are not touched. It works whatever the multi-factor setting is.</p>
      </>}
      {out && <>
        {out.done.length > 0 && <p className="status ok">Asked: {out.done.map((d) => `${d.username}${d.signed_out ? "" : " (not signed out)"}${d.emailed ? ", emailed" : ""}`).join("; ")}.</p>}
        {out.refused.map((r) => <p key={r.username} className="status bad">{r.username}: {r.why}</p>)}
      </>}
      {error && <p className="status bad">{error}</p>}
    </Modal>
  );
}

// R3.3 (owner, 13 Nov 2026: "Just Have list of projects and roles on them and another List of models with roles on it. Two
// different tables. Remove tree just two lists in columns"): each person's projects and models, one per line, with roles.
const PROJECT_ROLES = { "project-admin": "Project Admin", "lead-architect": "Lead Architect", architect: "Architect",
  "model-admin": "Model Admin", "model-sub-admin": "Model Sub Admin", stakeholder: "Stakeholder" };
export const projectRoleName = (r) => PROJECT_ROLES[r] || r;

export function RoleList({ items, name, link }) {
  if (!items || !items.length) return <span className="quiet">none</span>;
  return (
    <ul className="role-list">
      {items.map((x) => (
        <li key={x.id}>{link ? <a href={link(x)}>{x.name}</a> : x.name} <span className="quiet">({(x.roles || [x.role]).map(name).join(", ")})</span></li>))}
    </ul>
  );
}

function useLoad(path, deps = []) {
  const [state, setState] = useState({ data: null, error: "" });
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, error: "" }));
    apiFetch(path).then((data) => live && setState({ data, error: "" })).catch((e) => live && setState({ data: null, error: e.message }));
    return () => { live = false; };
  }, [path, n, ...deps]);  // eslint-disable-line react-hooks/exhaustive-deps
  return { ...state, reload: () => setN((x) => x + 1) };
}

function People() {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => { const t = setTimeout(() => setQ(search), 300); return () => clearTimeout(t); }, [search]);
  const { data, error } = useLoad(`/api/v1/people${q ? `?search=${encodeURIComponent(q)}` : ""}`);
  const mfa = useLoad("/api/v1/people/mfa");
  const manage = can("users.manage");
  const [picked, setPicked] = useState([]);
  const [asking, setAsking] = useState(false);
  const pick = (u, on) => setPicked((x) => (on ? [...x, u] : x.filter((y) => y !== u)));
  const [role, setRole] = useState("");
  const rows = useMemo(() => (data || []).filter((p) => !role || (role === "none" ? !p.roles.length : p.roles.includes(role))), [data, role]);
  return (
    <>
      <div className="toolbar">
        <input className="search" placeholder="Search name, user name or email" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Global role">
          <option value="">Every role</option>
          {["super-admin", "it-admin", "user-admin", "keycloak-admin", "model-creator", "user"]
            .map((r) => <option key={r} value={r}>{roleName(r)}</option>)}
          <option value="none">No global role</option>
        </select>
        <button disabled={!rows.length} onClick={() => downloadCsv([["User", "Name", "Email", "EA Explorer roles", "Keycloak roles", "Projects", "Models"],
          ...rows.map((p) => [p.username, p.name || "", p.email || "", p.roles.map(roleName).join("; "), p.keycloak_roles.join("; "),
            (p.projects || []).map((x) => `${x.name} (${(x.roles || [x.role]).map(projectRoleName).join(", ")})`).join("; "),
            p.models.map((m) => `${m.name} (${(m.roles || [m.role]).join(", ")})`).join("; ")])], "people and roles")}>CSV</button>
        {manage && <button disabled={!picked.length} onClick={() => setAsking(true)}
          title="Ask the people ticked to set up their authenticator app again (a lost or new phone)">Set up the authenticator again...</button>}
        <span className="er-spacer" />
        <span className="quiet">{data ? `${rows.length} shown${data.length >= 100 ? " (first 100: search to narrow)" : ""}` : ""}</span>
      </div>
      <p className="quiet">Global roles are given in Keycloak, not here: use <em>Change in Keycloak</em>. Roles on a model are given on that model's <em>People</em> tab, roles on a project on the project's members.</p>
      {error && <p className="status bad">{error}</p>}
      {!data && !error && <p className="quiet">Reading people from Keycloak...</p>}
      {data && (
        <table className="grid-table">
          <thead><tr>{manage && <th aria-label="Pick" />}<th>Person</th><th>Authenticator</th><th>Global roles</th><th>Keycloak roles</th><th>Projects and roles</th><th>Models and roles</th><th /></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id} className={p.enabled ? "" : "retired"}>
                {manage && <td><input type="checkbox" aria-label={`Pick ${p.username}`} checked={picked.includes(p.username)}
                  onChange={(e) => pick(p.username, e.target.checked)} /></td>}
                <td><strong>{p.username}</strong>{p.name && <><br /><span className="quiet">{p.name}</span></>}{p.email && <><br /><span className="quiet small">{p.email}</span></>}</td>
                <td className="small">{mfa.data ? (MFA_SHOWN[(mfa.data.states || {})[p.username]] || <span className="quiet">-</span>) : <span className="quiet">{mfa.error ? "not known" : "..."}</span>}</td>
                <td>{p.roles.length ? p.roles.map((r) => <span key={r} className="rchip on">{roleName(r)}</span>) : <span className="quiet">none</span>}</td>
                <td className="quiet small">{p.keycloak_roles.filter((r) => !["offline_access", "uma_authorization"].includes(r) && !r.startsWith("default-roles-")).join(", ")}</td>
                <td className="small"><RoleList items={p.projects} name={projectRoleName} link={(x) => `#/projects/${x.id}/organisation`} /></td>
                <td className="small"><RoleList items={p.models} name={roleName} link={can("models.all") ? (m) => `#/metamodel/${m.id}/people` : null} /></td>
                <td className="nowrap"><a className="small-link" href={p.keycloak_url} target="_blank" rel="noreferrer">Change in Keycloak ↗</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {asking && <MfaReset people={picked} onClose={() => setAsking(false)} onDone={() => { setPicked([]); mfa.reload(); }} />}
    </>
  );
}

function RoleMapping() {
  const roles = useLoad("/api/v1/roles");
  const kcRoles = useLoad("/api/v1/keycloak-roles");
  const mappings = useLoad("/api/v1/role-mappings");
  const [kc, setKc] = useState("");
  const [from, setFrom] = useState("role");        // a Keycloak role, or a directory group (phase 36, D503)
  const [app, setApp] = useState("");
  const [error, setError] = useState("");
  const editable = can("roles.map");
  const reload = () => { roles.reload(); mappings.reload(); kcRoles.reload(); };
  async function add(e) {
    e.preventDefault(); setError("");
    try { await apiFetch("/api/v1/role-mappings", { method: "POST", body: JSON.stringify({ keycloak_role: (from === "group" ? "group:" : "") + kc.trim().replace(/^group:/i, ""), app_role: app }) }); setKc(""); reload(); }
    catch (err) { setError(err.message); }
  }
  async function remove(m) {
    setError("");
    try { await apiFetch(`/api/v1/role-mappings/${m.id}`, { method: "DELETE" }); reload(); } catch (err) { setError(err.message); }
  }
  const byRole = {};
  for (const m of mappings.data || []) (byRole[m.app_role] ||= []).push(m);
  return (
    <>
      <p className="quiet">Global roles come from Keycloak: each Keycloak role below gives one EA Explorer global role. People are given the
        Keycloak roles in Keycloak, or belong to a <strong>directory group</strong>: an Active Directory group reaching Keycloak through
        its LDAP user federation, or an Entra ID group sent as a group claim (a group's name, or its object ID for Entra ID). Map a
        group here and everyone in it gets the role at their next sign-in. A change here applies within 30 seconds.
        Roles on a model (Model Admin, Architect, Model Sub Admin, Report Viewer) are not mapped: they are given on each model's People tab.</p>
      {(roles.error || mappings.error) && <p className="status bad">{roles.error || mappings.error}</p>}
      <table className="grid-table">
        <thead><tr><th>Global role</th><th>What it allows</th><th>Given by these Keycloak roles and directory groups</th></tr></thead>
        <tbody>
          {(roles.data || []).filter((r) => r.scope !== "model").map((r) => (
            <tr key={r.code}>
              <td><strong>{r.name}</strong><br /><code className="quiet">{r.code}</code></td>
              <td className="small">{r.description}</td>
              <td>{(byRole[r.code] || []).map((m) => (
                <span key={m.id} className="rchip" title={m.keycloak_role.startsWith("group:") ? "A directory group" : "A Keycloak role"}>
                  {m.keycloak_role.startsWith("group:") ? <>👥 {m.keycloak_role.slice(6)}</> : m.keycloak_role}
                  <button className="tiny" disabled={!editable} title={editable ? `Remove: ${m.keycloak_role} no longer gives ${r.name}` : `Changing the mapping: ${needsRole(["user-admin", "super-admin"])}`} onClick={() => remove(m)}>×</button></span>))}
                {!(byRole[r.code] || []).length && <span className="quiet">none: nobody has it</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {(
        <form className="toolbar" onSubmit={add} title={editable ? undefined : `Changing the mapping: ${needsRole(["user-admin", "super-admin"])}`}>
          <strong>Add a mapping:</strong>
          <select value={from} onChange={(e) => setFrom(e.target.value)} aria-label="Map a Keycloak role or a directory group">
            <option value="role">Keycloak role</option>
            <option value="group">Directory group</option>
          </select>
          <input list={from === "role" ? "kc-roles" : undefined} className="search" style={{ maxWidth: 240 }} value={kc} onChange={(e) => setKc(e.target.value)}
            placeholder={from === "role" ? "a realm role" : "a group name, e.g. EA Architects"} aria-label={from === "role" ? "Keycloak role" : "Directory group"} />
          <datalist id="kc-roles">{(kcRoles.data || []).map((r) => <option key={r.name} value={r.name}>{r.description}</option>)}</datalist>
          gives
          <select value={app} onChange={(e) => setApp(e.target.value)}>
            <option value="">Global role...</option>
            {(roles.data || []).filter((r) => r.scope !== "model").map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </select>
          <button type="submit" className="primary" disabled={!editable || !kc.trim() || !app}>Add</button>
        </form>
      )}
      {kcRoles.error && <p className="quiet small">Keycloak roles could not be listed ({kcRoles.error}); you can still type one.</p>}
      {error && <p className="status bad">{error}</p>}
    </>
  );
}

export default function Users({ route }) {
  const tab = route.split("?")[0].split("/")[3] || "people";   // #/admin/users/<people|mapping>
  if (!can("users.read")) return <p className="status bad">This page is for User Admins and Super Admins.</p>;
  return (
    <div>
      <h1>Users and roles</h1>
      <div className="tabs sub" role="tablist" aria-label="Users and roles">
        {[["people", "People"], ["mapping", "Keycloak role mapping"]].map(([k, l]) => (
          <a key={k} href={`#/admin/users/${k}`} className={`tab${tab === k ? " on" : ""}`} role="tab" aria-selected={tab === k}>{l}</a>
        ))}
      </div>
      <div className="tab-panel" role="tabpanel">{tab === "mapping" ? <RoleMapping /> : <People />}</div>
    </div>
  );
}
