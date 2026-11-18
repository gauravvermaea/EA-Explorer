// System Admin > Setup (Release 6.6, D750; reworked 18 Nov 2026, D772). The guides as documents: nothing is run from
// here (the owner, 12:29: "There should be no run it. Just document"). Each guide asks for its values first (the server's
// name, where the key file is, ...) and every command in it is filled in with them, ready to copy, for Windows or for
// Linux and macOS (12:29: "put in paramters like server name location of key file and so on and we get the dynamic set
// of commands"). The same list as `eax setup <guide> --set KEY=VALUE`, the Jenkins pipeline and docs/guides
// (eaxcli/setup.py).
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";

const VALUES_KEY = "eax-setup-values";       // this browser only: the values typed, so they are there next time
const OS_KEY = "eax-setup-os";
const PLACE = /<([A-Z][A-Z_]*)>/g;

function remembered(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; } catch { return fallback; }
}
function remember(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage blocked: typed again next time */ }
}

// <KEY> replaced by its value where one is given; in a command an optional value left empty takes its option with it
// (the same rule as eaxcli/setup.py fill)
export function fill(text, values, optional = [], command = false) {
  let t = text || "";
  if (command) {
    optional.forEach((k) => {
      if (!String(values[k] || "").trim()) t = t.replace(new RegExp(`\\s+(--[a-z-]+\\s+|-[A-Z][A-Za-z]+\\s+)?<${k}>`, "g"), "");
    });
  }
  return t.replace(PLACE, (m, k) => (String(values[k] || "").trim() ? String(values[k]).trim() : m));
}

function Filled({ text }) {          // a sentence with the values still to give shown as such
  const parts = (text || "").split(/(<[A-Z][A-Z_]*>)/);
  return <>{parts.map((p, i) => (/^<[A-Z][A-Z_]*>$/.test(p) ? <code key={i} className="setup-missing">{p}</code> : p))}</>;
}

async function copy(text, setSaid) {
  try { await navigator.clipboard.writeText(text); setSaid("Copied."); }
  catch { setSaid("Your browser did not allow copying: select the command and copy it."); }
  setTimeout(() => setSaid(""), 2500);
}

export default function SetupGuides() {
  const [guides, setGuides] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(null);
  useEffect(() => {
    apiFetch("/api/v1/admin/commands/guides").then((r) => setGuides(r.guides || [])).catch((e) => setErr(e.message));
  }, []);
  if (!can("system.operate")) return <p className="quiet">Setup is for IT Admins and Super Admins.</p>;
  if (err) return <p className="status bad">{err}</p>;
  if (!guides) return <p><span className="spinner" aria-hidden="true" /> Reading the guides…</p>;
  const g = guides.find((x) => x.id === open);
  if (g) return <Guide g={g} onBack={() => setOpen(null)} />;
  return (
    <div className="setup-guides">
      <p className="quiet">Each guide as a document: give your values once (the server's name, where the files are) and every
        command in it is filled in, ready to copy. Nothing runs from here. The same guides are <code>eax setup &lt;guide&gt;</code> on
        the machine, a pipeline in Jenkins, and the files in <code>docs/guides</code>.</p>
      <div className="cc-cards">
        {guides.map((x) => (
          <button key={x.id} className="cc-card" onClick={() => setOpen(x.id)}>
            <strong>{x.title}</strong>
            <span>{x.for}</span>
            <span className="quiet small">{x.steps.length} steps{x.params?.length ? `, ${x.params.length} value${x.params.length === 1 ? "" : "s"} to give` : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Guide({ g, onBack }) {
  const params = g.params || [];
  const optional = params.filter((p) => p.optional).map((p) => p.key);
  const [values, setValues] = useState(() => remembered(VALUES_KEY, {}));
  const [os, setOs] = useState(() => remembered(OS_KEY, /Windows/i.test(navigator.userAgent || "") ? "windows" : "unix"));
  const [said, setSaid] = useState({});
  const set = (k, v) => { const next = { ...values, [k]: v }; setValues(next); remember(VALUES_KEY, next); };
  const pickOs = (v) => { setOs(v); remember(OS_KEY, v); };
  const tell = (i) => (text) => setSaid((s) => ({ ...s, [i]: text }));
  const commandOf = (s) => fill(os === "windows" ? s.windows : s.unix, values, optional, true);
  const commands = g.steps.filter((s) => s.command).map(commandOf);
  const missing = params.filter((p) => !p.optional && !String(values[p.key] || "").trim());

  function download() {
    const lines = [`# ${g.title}`, "", `${g.for}.`, ""];
    if (params.length) {
      lines.push("## Your values", "");
      params.forEach((p) => lines.push(`- ${p.label}: ${String(values[p.key] || "").trim() || `<${p.key}> (not given)`}`));
      lines.push("");
    }
    lines.push(`## Steps (${os === "windows" ? "Windows, PowerShell" : "Linux or macOS"})`, "");
    g.steps.forEach((s, i) => {
      lines.push(`### ${i + 1}. ${s.title}`, "", fill(s.say, values), "");
      if (s.command) lines.push("```", commandOf(s), "```", "");
    });
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/markdown" }));
    const a = document.createElement("a");
    a.href = url; a.download = `${g.id}.md`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  return (
    <div className="setup-guide">
      <p><button className="link" onClick={onBack}>← The guides</button></p>
      <h3>{g.title}</h3>
      <p className="quiet">{g.for}. On the machine: <code>eax setup {g.id}</code>; written: <code>{g.doc}</code>.</p>

      {params.length > 0 && (
        <section className="setup-values">
          <h4>Your values</h4>
          <div className="ed-form">
            {params.map((p) => (
              <label key={p.key} className="ed-field">
                <span>{p.label} {p.optional && <span className="quiet">(may be left out)</span>}</span>
                <input value={values[p.key] || ""} placeholder={p.example} onChange={(e) => set(p.key, e.target.value)} />
              </label>))}
          </div>
          {missing.length > 0 && <p className="quiet small">Still to give: {missing.map((p) => p.label.toLowerCase()).join(", ")}.
            Until then the commands show where each goes.</p>}
        </section>)}

      <p className="setup-os">
        Commands for{" "}
        <label className="check inline"><input type="radio" checked={os === "windows"} onChange={() => pickOs("windows")} /> Windows (PowerShell)</label>{" "}
        <label className="check inline"><input type="radio" checked={os === "unix"} onChange={() => pickOs("unix")} /> Linux or macOS</label>
        {" · "}<button className="linkish" disabled={!commands.length} onClick={() => copy(commands.join("\n"), tell("all"))}>Copy every command</button>
        {" · "}<button className="linkish" onClick={download}>Download this guide</button>
        {said.all && <span className="quiet small"> {said.all}</span>}
      </p>

      <ol className="setup-steps">
        {g.steps.map((s, i) => (
          <li key={s.title}>
            <strong>{s.title}</strong>
            <p><Filled text={fill(s.say, values)} /></p>
            {s.command && (
              <div className="setup-command">
                <pre><code><Filled text={commandOf(s)} /></code></pre>
                <button onClick={() => copy(commandOf(s), tell(i))}>Copy</button>
                {said[i] && <span className="quiet small"> {said[i]}</span>}
              </div>)}
          </li>))}
      </ol>
    </div>
  );
}
