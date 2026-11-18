// A model's Import and export › Git (Release 6.5, D753; owner, 18 Nov 2026, 06:47: "git needs to be on Model > Manage >
// Import Export"): this model's package put on a git repository (Excel or zip; without data, with it, or with its
// history), and a package taken from a git repository: uploaded as a new model, as Upload does. The repository's
// address and branch are remembered in this browser; the user name and token are typed each time and never kept.
import { useState } from "react";
import { CONTENT_LEVELS, UploadWizard } from "./ModelOps";
import { GitFields, GitPicker, gitPush, gitReady, useGitPlace } from "./GitPlace";

export default function ModelGitTab({ m }) {
  const [g, set] = useGitPlace();
  const [format, setFormat] = useState("zip");
  const [content, setContent] = useState(m.kind === "template" ? "metamodel" : "content");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [taken, setTaken] = useState(null);
  async function push() {
    setBusy(true); setMsg({ ok: true, text: "" });
    try { const r = await gitPush(g, { source: "model", model: m.id, format, content }); setMsg({ ok: true, text: `Put on ${r.repository} (${r.branch}): ${r.pushed}` }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy(false);
  }
  return (
    <div className="model-git">
      <h3>Put this model on git</h3>
      <p className="quiet">One commit under <code>eax-packages/</code> in the repository, on any git server over HTTPS. Another site (or this one) takes it from there.</p>
      <div className="ed-form">
        <div className="seg small">
          <button type="button" className={format === "zip" ? "on" : ""} onClick={() => setFormat("zip")}>Zip (JSON and CSV)</button>
          <button type="button" className={format === "xlsx" ? "on" : ""} onClick={() => setFormat("xlsx")}>Excel workbook</button>
        </div>
        <div className="ed-radio">
          {CONTENT_LEVELS.map(([k, l, hint]) => (
            <label key={k} className="lock-opt" title={hint}>
              <input type="radio" name="git-content" checked={content === k} disabled={m.kind === "template" && k !== "metamodel"} onChange={() => setContent(k)} />
              <span><b>{l}</b></span>
            </label>))}
        </div>
        <GitFields g={g} set={set} />
        <div className="toolbar"><button className="primary" disabled={busy || !gitReady(g)} onClick={push}>{busy ? "Putting it on git..." : "Put it on git"}</button></div>
        {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}
      </div>
      <h3>Take a model from git</h3>
      <p className="quiet">List the packages in the repository and pick one: it is read and checked, then uploaded as a new model, as Upload does.</p>
      <GitPicker onFile={(f) => setTaken(f)} />
      {taken && <UploadWizard initialFile={taken} onClose={() => setTaken(null)} />}
    </div>
  );
}
