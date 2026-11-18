// System Admin › Settings import and export (Release 6.7, D755; owner, 17 Nov 2026, 22:06: "we need another release for
// import and export of settings and admin configs"). One file, every admin setting, the parts the Super Admin ticks;
// never content, people, a password, key or certificate. Import shows every difference first (here and in the file),
// the admin ticks what to take, a safety copy is kept first (Undo puts it back) and each change is in the audit trail.
// The same as `eax settings export|import` and the Jenkins pipelines; a git repository is one more place for the file.
import { useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { refreshAll, useApi } from "./ModelViews";
import { Modal } from "./ModelOps";
import { GitPicker, GitPushDialog } from "./GitPlace";
import { fmtDateTime } from "./fmt";

const post = (path, body) => apiFetch(path, { method: "POST", body: JSON.stringify(body || {}) });
const shown = (v) => (v === null || v === undefined ? "(not here)" : typeof v === "string" ? v : JSON.stringify(v, null, 1));

function Parts({ parts, chosen, setChosen }) {
  const flip = (id) => setChosen(chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id]);
  return (
    <div className="settings-parts">
      {parts.map((p) => (
        <label key={p.id} className="check" title={p.carries}>
          <input type="checkbox" checked={chosen.includes(p.id)} onChange={() => flip(p.id)} /> {p.title}
          <span className="quiet small"> {p.carries}</span>
        </label>))}
      <p className="small">
        <button className="linkish" onClick={() => setChosen(parts.map((p) => p.id))}>All</button>{" · "}
        <button className="linkish" onClick={() => setChosen([])}>None</button>
      </p>
    </div>
  );
}

function Preview({ preview, file, onDone }) {
  const diffs = preview.differences || {};
  const start = {};
  Object.entries(diffs).forEach(([p, d]) => { start[p] = (d.differences || []).filter((r) => !r.cannot).map((r) => r.key); });
  const [picks, setPicks] = useState(start);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const total = Object.values(picks).reduce((n, k) => n + k.length, 0);
  const flip = (p, k) => {
    const cur = picks[p] || [];
    setPicks({ ...picks, [p]: cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k] });
  };
  async function take() {
    setBusy(true); setErr("");
    try {
      const chosen = Object.fromEntries(Object.entries(picks).filter(([, k]) => k.length));
      onDone(await post("/api/v1/admin/settings-transfer/import", { file, picks: chosen }));
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }
  const f = preview.file || {};
  return (
    <div className="settings-import-preview">
      <p>The file: made {f.made_at ? fmtDateTime(f.made_at) : "?"} by {f.made_by || "?"} on {f.site || "a site"}, release {f.release || "?"}.
        Nothing has changed yet.</p>
      {Object.entries(diffs).map(([p, d]) => (
        <section key={p} className="settings-part">
          <h4>{d.title} <span className="quiet small">
            {(d.differences || []).length} difference(s), {d.same} the same{d.only_here?.length ? `, ${d.only_here.length} only here (kept)` : ""}</span></h4>
          {(d.differences || []).length > 0 && (
            <table className="data settings-diff">
              <thead><tr><th>Take</th><th>Item</th><th>Here</th><th>In the file</th></tr></thead>
              <tbody>{d.differences.map((r) => (
                <tr key={r.key} className={r.cannot ? "muted" : ""}>
                  <td><input type="checkbox" disabled={!!r.cannot} checked={(picks[p] || []).includes(r.key)} onChange={() => flip(p, r.key)} /></td>
                  <td><code>{r.key}</code> <span className="quiet small">{r.change === "new" ? "new" : "changed"}</span>
                    {r.cannot && <div className="status bad small">{r.cannot}</div>}
                    {r.maintenance && <div className="status warn small">Turning this on: {r.maintenance}; the maintenance page will go up when it runs (you are asked first).</div>}</td>
                  <td><pre className="settings-value">{shown(r.here)}</pre></td>
                  <td><pre className="settings-value">{shown(r.file)}</pre></td>
                </tr>))}</tbody>
            </table>)}
        </section>))}
      {Object.entries(preview.not_read || {}).map(([p, why]) => <p key={p} className="status warn">{p}: not read here ({why})</p>)}
      {err && <p className="status bad">{err}</p>}
      <button className="primary" disabled={busy || !total} onClick={take}>
        {busy ? "Taking..." : `Take the ${total} ticked (a safety copy first)`}</button>
    </div>
  );
}

export default function SettingsTransfer() {
  const { data, error } = useApi("/api/v1/admin/settings-transfer");
  const parts = data?.parts || [];
  const [chosen, setChosen] = useState(null);
  const [gitOpen, setGitOpen] = useState(false);
  const [file, setFile] = useState(null);           // the chosen file's text
  const [fileName, setFileName] = useState("");
  const [fromGit, setFromGit] = useState(false);
  const [preview, setPreview] = useState(null);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [busy, setBusy] = useState("");
  const ticked = chosen ?? parts.map((p) => p.id);

  async function exportFile() {
    setBusy("export"); setMsg({ ok: true, text: "" });
    try { await apiDownload("/api/v1/admin/settings-transfer/export", "eax-settings.json", { parts: ticked }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy("");
  }
  async function read(f) {
    setMsg({ ok: true, text: "" }); setPreview(null);
    const text = await f.text();
    setFile(text); setFileName(f.name); setFromGit(false);
    setBusy("preview");
    try { setPreview(await post("/api/v1/admin/settings-transfer/preview", { file: text, parts: ticked })); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy("");
  }
  function done(out) {
    const n = Object.values(out.taken || {}).reduce((a, k) => a + k.length, 0);
    setPreview(null); setFile(null);
    setMsg({ ok: true, text: [`Taken: ${n} difference(s).`, ...(out.refused || []), ...(out.said || []),
      out.copy ? "The settings as they were are kept below: Undo puts them back." : ""].filter(Boolean).join(" ") });
    refreshAll();                                   // every screen reads the new settings, this one its copies
  }
  async function undo(c) {
    if (!window.confirm(`Put back the settings kept ${fmtDateTime(c.made_at)} (${(c.parts || []).join(", ")})? The settings now are kept first, so this can be undone too.`)) return;
    setBusy(c.id); setMsg({ ok: true, text: "" });
    try { done(await post("/api/v1/admin/settings-transfer/undo", { copy: c.id })); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy("");
  }

  if (error) return <p className="status bad">{error}</p>;
  return (
    <div className="settings-transfer">
      <h2>Settings import and export</h2>
      <p className="quiet">Every admin setting in one file, the parts you tick: to copy a site's set-up to another, or to keep
        it before a change. Never content (models and projects have their own packages), people, a password, key or certificate.
        The same as <code>eax settings export</code> and <code>eax settings import</code>, and their Jenkins pipelines.</p>

      <h3>The parts</h3>
      <Parts parts={parts} chosen={ticked} setChosen={setChosen} />

      <h3>Export</h3>
      <p>
        <button className="primary" disabled={!ticked.length || !!busy} onClick={exportFile}>{busy === "export" ? "Making the file..." : "Export to a file"}</button>{" "}
        <button disabled={!ticked.length} onClick={() => setGitOpen(true)}>Put on git</button>
      </p>

      <h3>Import</h3>
      <p className="quiet small">First every difference is shown and nothing changes; you tick what to take. A safety copy of
        the settings here is kept first. Nothing here is ever removed. A file from a newer release is refused.</p>
      <p>
        <label className="button-like">Choose a settings file
          <input type="file" accept=".json,application/json" hidden onChange={(e) => e.target.files[0] && read(e.target.files[0])} /></label>{" "}
        <button className="linkish" onClick={() => setFromGit(!fromGit)}>{fromGit ? "Not from git" : "From git"}</button>
      </p>
      {fromGit && <GitPicker suffix=".json" onFile={read} />}
      {busy === "preview" && <p className="quiet">Comparing {fileName} with this installation...</p>}
      {preview && <Preview key={`${fileName}:${preview.file?.made_at}`} preview={preview} file={file} onDone={done} />}
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`}>{msg.text}</p>}

      <h3>Safety copies</h3>
      {!(data?.copies || []).length ? <p className="quiet">None yet: one is kept before each import.</p> : (
        <table className="data">
          <thead><tr><th>Kept</th><th>By</th><th>Before</th><th>Parts</th><th /></tr></thead>
          <tbody>{data.copies.map((c) => (
            <tr key={c.id}>
              <td>{fmtDateTime(c.made_at)}</td><td>{c.made_by}</td><td>{c.why === "undo" ? "an undo" : "an import"}</td>
              <td>{(c.parts || []).join(", ")}</td>
              <td>{c.undone ? <span className="quiet">put back</span> : null}{" "}
                <button disabled={!!busy} onClick={() => undo(c)}>{busy === c.id ? "Putting back..." : "Undo"}</button></td>
            </tr>))}</tbody>
        </table>)}

      {gitOpen && <GitPushDialog title="Put the settings file on git" Modal={Modal} onClose={() => setGitOpen(false)}
        source={{ source: "settings", parts: ticked }} />}
    </div>
  );
}
