// The front door's certificate (Release 6.6, R6.6.3, D750): the one people's browsers see for EA Explorer, Reports and
// Documents. A Super Admin or an IT Admin uploads the organisation's certificate, its chain and its key; it is checked
// first (names, dates, the key, the chain) and refused in words when wrong, then put in place and reloaded with no
// restart. The one in use is kept: Undo puts it back. The key is never shown again.
import { useState } from "react";
import { apiFetch } from "./auth";
import { useApi } from "./ModelViews";

const readFile = (f) => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(String(r.result)); r.onerror = bad; r.readAsText(f); });

export default function FrontCertificate() {
  const [gen, setGen] = useState(0);
  const { data, error } = useApi(`/api/v1/admin/front-certificate?g=${gen}`);
  const [files, setFiles] = useState({ certificate: "", chain: "", key: "" });
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [busy, setBusy] = useState(false);
  const pick = (k) => async (e) => { const f = e.target.files?.[0]; setFiles({ ...files, [k]: f ? await readFile(f) : "" }); };
  async function upload() {
    setBusy(true); setMsg({ ok: true, text: "" });
    try {
      const r = await apiFetch("/api/v1/admin/front-certificate", { method: "POST", body: JSON.stringify(files) });
      setMsg({ ok: true, text: `In use now (${r.how}): ${r.subject}, issued by ${r.issuer}, until ${String(r.not_after).slice(0, 10)}${r.warning ? `; note: ${r.warning}` : ""}.` });
      setFiles({ certificate: "", chain: "", key: "" }); setGen((g) => g + 1);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    setBusy(false);
  }
  async function undo() {
    if (!window.confirm("Put back the certificate that was in use before the last upload?")) return;
    try { const r = await apiFetch("/api/v1/admin/front-certificate", { method: "DELETE" }); setMsg({ ok: true, text: `Put back (${r.how}).` }); setGen((g) => g + 1); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  }
  const p = data?.presented;
  return (
    <div className="front-cert">
      <h3>Front door certificate</h3>
      <p className="quiet">What browsers see for {(data?.needs || []).join(", ")}. Upload your organisation's certificate, its chain and its key:
        it is checked first, then used at once with no restart; the one in use is kept so you can undo. A laptop may keep its own.</p>
      {error && <p className="status bad">{error}</p>}
      {p && (p.error ? <p className="status warn">{p.error}</p> : (
        <p>In use: <b>{p.subject}</b>, issued by {p.self_signed ? "itself (self-signed: browsers warn)" : p.issuer}; names {p.names.join(", ") || "none"};
          until {String(p.not_after).slice(0, 10)} (<span className={p.days_left <= 30 ? "warn-text" : ""}>{p.days_left} days</span>).</p>))}
      <div className="front-cert-files">
        <label>Certificate (PEM) <input type="file" accept=".crt,.pem,.cer" onChange={pick("certificate")} /></label>
        <label>Chain (PEM, the authorities in order; may be in the certificate file) <input type="file" accept=".crt,.pem,.cer" onChange={pick("chain")} /></label>
        <label>Private key (PEM, no password) <input type="file" accept=".key,.pem" onChange={pick("key")} /></label>
      </div>
      <div className="toolbar">
        <button className="primary" disabled={busy || !files.certificate || !files.key} onClick={upload}>{busy ? "Checking..." : "Check and use it"}</button>
        <button onClick={undo}>Undo the last upload</button>
      </div>
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}
    </div>
  );
}
