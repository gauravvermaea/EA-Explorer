// People's skills (owner, 9 Nov 2026, D353): each user adds their own on My profile (#/my-profile); the Skills
// repository (#/repository/skills) lists every EA Explorer user (from Keycloak) with theirs, by skill and by person.
import { useEffect, useState } from "react";
import { apiFetch, myInfo, roleName, roles } from "./auth";
import { refreshAll, useApi } from "./ModelViews";
import { fmtDateTime } from "./fmt";
import { MyLook } from "./branding";

export function SkillTags({ value, onChange, suggestions = [], disabled }) {
  const [t, setT] = useState("");
  const add = (s) => {
    const k = s.split(",").map((x) => x.trim().replace(/\s+/g, " ")).filter(Boolean);
    const next = [...value];
    for (const x of k) if (!next.some((y) => y.toLowerCase() === x.toLowerCase())) next.push(x.slice(0, 60));
    onChange(next); setT("");
  };
  const offered = suggestions.filter((s) => !value.some((v) => v.toLowerCase() === s.toLowerCase()));
  return (
    <div className="skill-tags">
      <div className="skill-chips">
        {value.map((s) => <span key={s} className="chip skill-chip">{s}{!disabled &&
          <button className="linkish" aria-label={`Remove ${s}`} onClick={() => onChange(value.filter((x) => x !== s))}>✕</button>}</span>)}
        {!value.length && <span className="quiet small">No skills yet.</span>}
      </div>
      {!disabled && <form className="row-gap" onSubmit={(e) => { e.preventDefault(); if (t.trim()) add(t); }}>
        <input value={t} onChange={(e) => setT(e.target.value)} list="all-skills" placeholder="Add a skill (commas for several)" aria-label="Add a skill" style={{ minWidth: 300 }} />
        <datalist id="all-skills">{offered.map((s) => <option key={s} value={s} />)}</datalist>
        <button type="submit" disabled={!t.trim()}>Add</button>
      </form>}
    </div>
  );
}

// the TOGAF architect roles a person holds and their level in each category of architecture skill (Release 12, R12.8;
// TOGAF Series Guides G198 and G249), beside their own skills
function TogafSkills({ togaf, value, onChange }) {
  const flip = (r) => onChange({ ...value, roles: value.roles.includes(r) ? value.roles.filter((x) => x !== r) : [...value.roles, r] });
  return (
    <div className="ba-box" style={{ marginTop: 10 }}>
      <h3>TOGAF roles and skill levels</h3>
      <p className="quiet small">The architect roles you hold, and how proficient you are in each category of architecture skill:
        {" "}{togaf.levels.map((l) => `${l.level} ${l.name}`).join(", ")}. Leave a category blank if you would rather not say.</p>
      <div>{togaf.roles.map((r) => <label key={r} className={`choice${value.roles.includes(r) ? " on" : ""}`}>
        <input type="checkbox" checked={value.roles.includes(r)} onChange={() => flip(r)} /> {r}</label>)}</div>
      <table className="grid-table small"><tbody>{togaf.categories.map((c) => (
        <tr key={c.key}><td><b>{c.name}</b> <span className="quiet">{c.covers}</span></td>
          <td><select value={value.levels[c.key] || ""} aria-label={`My level in ${c.name}`}
            onChange={(e) => onChange({ ...value, levels: { ...value.levels, [c.key]: e.target.value ? Number(e.target.value) : undefined } })}>
            <option value="">not said</option>
            {togaf.levels.map((l) => <option key={l.level} value={l.level} title={l.means}>{l.level} {l.name}</option>)}</select></td></tr>))}</tbody></table>
    </div>
  );
}

export default function MyProfile() {
  const me = myInfo() || {};
  const { data, error } = useApi("/api/v1/me/skills");
  const [skills, setSkills] = useState(null);
  const [tg, setTg] = useState(null);           // TOGAF roles and skill levels (Release 12, R12.8)
  const [msg, setMsg] = useState({ ok: true, text: "" });
  useEffect(() => { if (data && skills === null) setSkills(data.skills); }, [data, skills]);
  useEffect(() => { if (data && tg === null) setTg({ roles: data.togaf_roles || [], levels: data.togaf_levels || {} }); }, [data, tg]);
  async function save() {
    try {
      const r = await apiFetch("/api/v1/me/skills", { method: "PUT", body: JSON.stringify({ skills, togaf_roles: tg?.roles, togaf_levels: tg?.levels }) });
      setMsg({ ok: true, text: r.message }); refreshAll(); setTg(null);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  const tgChanged = data && tg && (JSON.stringify(tg.roles) !== JSON.stringify(data.togaf_roles || [])
    || JSON.stringify(Object.entries(tg.levels).filter(([, v]) => v).sort()) !== JSON.stringify(Object.entries(data.togaf_levels || {}).sort()));
  const changed = data && skills && (JSON.stringify(skills) !== JSON.stringify(data.skills) || tgChanged);
  return (
    <section className="page">
      <h1>My profile</h1>
      <p className="quiet small">Press / (or Ctrl+K) anywhere to find a function or content.</p>
      <table className="facts">
        <tbody>
          <tr><th>Name</th><td>{me.name || me.username}</td></tr>
          <tr><th>User name</th><td>{me.username}</td></tr>
          <tr><th>Roles</th><td>{roles().length ? roles().map(roleName).join(", ") : "none yet"}</td></tr>
          {me.email && <tr><th>Email</th><td>{me.email}</td></tr>}
        </tbody>
      </table>
      <h2>My skills</h2>
      <p className="quiet">What you know and do: any words you like (tools, methods, domains, industries). They show beside your name in the
        <a href="#/repository/skills"> Skills repository</a> and on the Organisation tab of the projects you are on. The skills other people use
        are offered as you type, so the same skill is spelled the same way.</p>
      {error && <p className="status bad">{error}</p>}
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`}>{msg.text}</p>}
      {skills === null ? (!error && <p className="quiet">Loading…</p>) : <>
        <SkillTags value={skills} onChange={setSkills} suggestions={data?.suggestions || []} />
        {data?.togaf && tg && <TogafSkills togaf={data.togaf} value={tg} onChange={setTg} />}
        <div className="row-gap" style={{ marginTop: 10 }}>
          <button className="primary" disabled={!changed} onClick={save}>Save my skills</button>
          {changed && <button onClick={() => { setSkills(data.skills); setTg(null); }}>Undo my edits</button>}
          {data?.modified_at && <span className="small quiet">Last saved {fmtDateTime(data.modified_at)}</span>}
        </div>
      </>}
      <MyLook />
    </section>
  );
}

// the Skills repository by TOGAF role, with each person's level in each category (Release 12, R12.8)
function TogafRepository({ data, label, byName }) {
  const cats = data.togaf.categories;
  const lvl = Object.fromEntries(data.togaf.levels.map((l) => [l.level, l.name]));
  const anyone = Object.values(data.by_role).some((x) => x.length);
  return (
    <div>
      {!anyone && <p className="quiet">No one has said which TOGAF roles they hold yet. Say yours on <a href="#/my-profile">My profile</a>.</p>}
      {data.togaf.roles.filter((r) => data.by_role[r].length).map((r) => (
        <div key={r} className="ba-box"><h3>{r} <span className="small quiet">{data.by_role[r].length}</span></h3>
          <table className="grid-table small"><thead><tr><th>Person</th>{cats.map((c) => <th key={c.key} title={c.covers}>{c.name}</th>)}</tr></thead>
            <tbody>{data.by_role[r].map((u) => { const p = byName[u] || { username: u, togaf_levels: {} }; return (
              <tr key={u}><td>{label(p)}</td>{cats.map((c) => <td key={c.key} title={lvl[p.togaf_levels?.[c.key]] || "not said"}>
                {p.togaf_levels?.[c.key] || <span className="quiet">–</span>}</td>)}</tr>); })}</tbody></table></div>))}
    </div>
  );
}

// the organisation's Skills repository: every user, with their own skills
export function SkillsRepository() {
  const { data, error } = useApi("/api/v1/repository/skills");
  const [q, setQ] = useState("");
  const [skill, setSkill] = useState("");
  const [view, setView] = useState("skills");
  if (error) return <p className="status bad">{error}</p>;
  if (!data) return <p className="quiet">Loading…</p>;
  const ql = q.trim().toLowerCase();
  const has = (u, s) => u.skills.some((x) => x.toLowerCase() === s.toLowerCase());
  const users = data.users.filter((u) => (!skill || has(u, skill)) && (!ql || `${u.name} ${u.username} ${u.skills.join(" ")}`.toLowerCase().includes(ql)));
  const byName = Object.fromEntries(data.users.map((u) => [u.username, u]));
  const label = (u) => u.name || u.username;
  return (
    <div>
      <p className="quiet">Every EA Explorer user ({data.users.length}) with the skills
        they gave themselves on <a href="#/my-profile">My profile</a>. {data.without ? `${data.without} have none yet.` : ""} Add yours on <a href="#/my-profile">My profile</a>.</p>
      <div className="row-gap">
        <div className="cf-views" role="tablist">
          <button role="tab" aria-selected={view === "skills"} className={`cf-view${view === "skills" ? " on" : ""}`} onClick={() => setView("skills")}>By skill</button>
          <button role="tab" aria-selected={view === "people"} className={`cf-view${view === "people" ? " on" : ""}`} onClick={() => setView("people")}>By person</button>
          {data.togaf && <button role="tab" aria-selected={view === "togaf"} className={`cf-view${view === "togaf" ? " on" : ""}`} onClick={() => setView("togaf")}>By TOGAF role</button>}
        </div>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a person or skill" aria-label="Find" />
        <select value={skill} onChange={(e) => setSkill(e.target.value)} aria-label="Skill"><option value="">Any skill</option>
          {data.skills.map((s) => <option key={s.skill} value={s.skill}>{s.skill} ({s.people.length})</option>)}</select>
      </div>
      {view === "togaf" ? <TogafRepository data={data} label={label} byName={byName} /> : view === "skills" ? (
        <div className="level-cols">
          {data.skills.filter((s) => (!skill || s.skill === skill) && (!ql || s.skill.toLowerCase().includes(ql) || s.people.some((p) => `${label(byName[p] || { username: p })}`.toLowerCase().includes(ql))))
            .map((s) => (
              <div key={s.skill} className="level-col"><h3>{s.skill} <span className="small quiet">{s.people.length}</span></h3>
                {s.people.map((p) => <div key={p} className={`level-item${p === data.me ? " skill-me" : ""}`}>{label(byName[p] || { username: p })}
                  {byName[p]?.name && <span className="small quiet"> {p}</span>}</div>)}
              </div>
            ))}
          {!data.skills.length && <p className="quiet">No one has added skills yet. Add yours on <a href="#/my-profile">My profile</a>.</p>}
        </div>
      ) : (
        <table className="grid-table">
          <thead><tr><th>Person</th><th>User name</th><th>Skills</th></tr></thead>
          <tbody>
            {users.map((u) => <tr key={u.username} className={u.username === data.me ? "skill-me" : ""}>
              <td>{label(u)}{!u.enabled && <span className="small quiet"> (disabled)</span>}</td><td className="small">{u.username}</td>
              <td>{u.skills.length ? u.skills.map((s) => <button key={s} className="tag-chip" onClick={() => setSkill(s)}>{s}</button>)
                : <span className="small quiet">none yet{u.username === data.me ? <> · <a href="#/my-profile">add yours</a></> : ""}</span>}</td></tr>)}
            {!users.length && <tr><td colSpan={3} className="quiet">Nothing matches.</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}
