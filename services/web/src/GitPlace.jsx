// A git repository as one more place for packages (Release 6.5, D753; owner, 17 Nov 2026, 20:51: "github being just one
// more item ... zip is already there"). The Download of a model and a project's backup can go to a git repository on any
// git server (HTTPS); the Upload can take one from there. The repository's address and branch are remembered in this
// browser only; the user name and token are typed each time and never kept, here or on the server.
import { useState } from "react";
import { apiBlob, apiFetch, signedIn } from "./auth";

// a field as the forms show it (ModelOps' Field, written here so the two files do not import each other)
function Field({ label, hint, tip, children }) {
  return (
    <label className="ed-field">
      <span title={tip}>{label} {hint && <span className="quiet">{hint}</span>}</span>
      {children}
    </label>
  );
}

const KEY = "eax-git-place";

function remembered() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
}

export function useGitPlace() {
  const r = remembered();
  const [g, setG] = useState({ repo: r.repo || "", branch: r.branch || "main", username: "", token: "" });
  const set = (k, v) => {
    const next = { ...g, [k]: v };
    setG(next);
    try { localStorage.setItem(KEY, JSON.stringify({ repo: next.repo, branch: next.branch })); } catch { /* storage blocked: typed again */ }
  };
  return [g, set];
}

export function GitFields({ g, set }) {
  return (
    <div className="git-fields">
      <Field label="Repository" tip="Its HTTPS address on any git server. Packages go under eax-packages/ in it.">
        <input value={g.repo} onChange={(e) => set("repo", e.target.value)} placeholder="https://git.example.org/ea/packages.git" />
      </Field>
      <Field label="Branch"><input value={g.branch} onChange={(e) => set("branch", e.target.value)} /></Field>
      <Field label="User name" hint="(if the server asks)"><input value={g.username} onChange={(e) => set("username", e.target.value)} autoComplete="off" /></Field>
      <Field label="Token or password" tip="Used for this one call and never kept.">
        <input type="password" value={g.token} onChange={(e) => set("token", e.target.value)} autoComplete="new-password" />
      </Field>
    </div>
  );
}

export const gitReady = (g) => /^https:\/\/\S+\/\S+$/.test(g.repo || "");

export async function gitPush(g, source) {
  return apiFetch("/api/v1/git/push", { method: "POST", body: JSON.stringify({ ...g, ...source }) });
}

// Lists a repository's packages and hands the one chosen back as a File, as if it had been chosen on this computer.
export function GitPicker({ suffix = "", onFile }) {
  const [g, set] = useGitPlace();
  const [files, setFiles] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  async function list() {
    setBusy("list"); setErr("");
    try { setFiles((await apiFetch("/api/v1/git/list", { method: "POST", body: JSON.stringify({ ...g, suffix }) })).files); }
    catch (e) { setErr(e.message); }
    setBusy("");
  }
  async function take(file) {
    setBusy(file); setErr("");
    try {
      const blob = await apiBlob("/api/v1/git/fetch", { ...g, file });
      onFile(new File([blob], file));
    } catch (e) { setErr(e.message); }
    setBusy("");
  }
  if (!signedIn()) return null;
  return (
    <div className="git-picker">
      <GitFields g={g} set={set} />
      <button onClick={list} disabled={!gitReady(g) || !!busy}>{busy === "list" ? "Reading..." : "List the packages"}</button>
      {files && (files.length === 0 ? <p className="quiet small">No packages in eax-packages/ on that branch.</p> : (
        <ul className="git-files">{files.map((f) => (
          <li key={f}><button className="linkish" disabled={!!busy} onClick={() => take(f)}>{busy === f ? "Taking..." : f}</button></li>))}</ul>))}
      {err && <p className="status bad">{err}</p>}
    </div>
  );
}

// "Put on git" for a file made elsewhere on the screens (a project's backup file): the repository's fields and one button.
export function GitPushDialog({ title, source, onClose, Modal }) {
  const [g, set] = useGitPlace();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  async function push() {
    setBusy(true); setMsg({ ok: true, text: "" });
    try { const r = await gitPush(g, source); setMsg({ ok: true, text: `Put on ${r.repository} (${r.branch}): ${r.pushed}` }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy(false);
  }
  return (
    <Modal title={title} onClose={onClose}
      actions={<><button onClick={onClose}>Close</button><button className="primary" disabled={busy || !gitReady(g)} onClick={push}>{busy ? "Putting it on git..." : "Put it on git"}</button></>}>
      <div className="ed-form">
        <p className="quiet small">One commit under eax-packages/ in the repository; another site takes it with Upload, from the same repository.</p>
        <GitFields g={g} set={set} />
        {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`}>{msg.text}</p>}
      </div>
    </Modal>
  );
}
