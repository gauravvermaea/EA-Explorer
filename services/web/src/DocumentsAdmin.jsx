// System Admin › Settings › Documents (D903; owner, 23 Nov 2026, 22:45 to 22:54): Documents' OCR on or off (off unless
// chosen), when it may run (any time, or only in a window, at night say), and while it runs how far it has got, read again every few
// seconds. Only a Super Admin changes them; IT Admins see them. Everyone sees the short form in the header (OcrStatus).
import { useEffect, useState } from "react";
import { apiFetch, can } from "./auth";
import { fmtDateTime } from "./fmt";

export function useOcr(every = 5000) {
  const [d, setD] = useState(null);
  useEffect(() => {
    let stop = false;
    let timer;
    const load = async () => {
      try { const r = await apiFetch("/api/v1/documents-ocr"); if (!stop) setD(r); } catch { /* kept */ }
      if (!stop) timer = setTimeout(load, every);
    };
    void load();
    return () => { stop = true; clearTimeout(timer); };
  }, [every]);
  return d;
}

export default function DocumentsAdmin() {
  const ocr = useOcr(5000);
  const [set, setSet] = useState(null);
  const [draft, setDraft] = useState({});
  const [msg, setMsg] = useState("");
  const [windowed, setWindowed] = useState(false);   // any time, or only between two times (owner, 24 Nov 2026, 05:43)
  const mine = can("settings.manage");
  useEffect(() => {
    apiFetch("/api/v1/admin/settings").then((r) => {
      const v = Object.fromEntries((r.documents || []).map((s) => [s.key, s.value]));
      setSet(v); setDraft(v); setWindowed(!!(v.documents_ocr_from && v.documents_ocr_to));
    }).catch((e) => setMsg(e.message));
  }, []);
  const save = async (changes) => {
    setMsg("");
    try {
      const out = await apiFetch("/api/v1/admin/settings", { method: "PUT", body: JSON.stringify(changes) });
      const v = Object.fromEntries((out.values ? Object.entries(out.values) : []).filter(([k]) => k.startsWith("documents_ocr")));
      setSet((s) => ({ ...s, ...v })); setDraft((s) => ({ ...s, ...v })); setMsg(out.note || "Saved.");
    } catch (e) { setMsg(e.message); }
  };
  if (!set) return msg ? <p className="status bad">{msg}</p> : <p className="quiet">Loading...</p>;
  const changedWindow = draft.documents_ocr_from !== set.documents_ocr_from || draft.documents_ocr_to !== set.documents_ocr_to;
  return (
    <div className="documents-admin">
      <h2>Documents: read scanned pages (OCR)</h2>
      <p className="quiet">Off unless you choose it. On, Documents reads every page of each document as a picture, so scanned paper and
        photos of pages can be searched; switching it on also reads the documents already there (the industry packs alone are thousands
        of pages: an hour or more on a laptop). Off, each document's own text is still extracted and searched, and the OCR jobs waiting
        are cleared.</p>
      <label className="switch-label">
        <input type="checkbox" checked={!!set.documents_ocr} disabled={!mine} onChange={(e) => save({ documents_ocr: e.target.checked })} />
        {" "}Read scanned pages (OCR): <b>{set.documents_ocr ? "on" : "off"}</b></label>
      {!mine && <p className="small quiet">Only a Super Admin changes this.</p>}

      <h3>When it runs</h3>
      <p className="small quiet">Any time it is on (the default), or only between two times (local), 22:00 to 06:00 say, so documents
        are read at night; outside them the pages waiting are held and reading carries on in the next window.</p>
      <div className="row-gap">
        <label title="Documents reads scanned pages whenever OCR is on: no window">
          <input type="radio" name="ocr-when" checked={!windowed} disabled={!mine}
            onChange={() => { setWindowed(false); if (set.documents_ocr_from || set.documents_ocr_to) save({ documents_ocr_from: "", documents_ocr_to: "" }); }} />
          {" "}Any time</label>
        <label title="Documents reads scanned pages only between the two times below, at night say">
          <input type="radio" name="ocr-when" checked={windowed} disabled={!mine} onChange={() => setWindowed(true)} />
          {" "}Only between</label>
      </div>
      {windowed && (
        <div className="row-gap">
          <label>From <input aria-label="OCR runs from" placeholder="22:00" size={6} value={draft.documents_ocr_from || ""} disabled={!mine}
            onChange={(e) => setDraft({ ...draft, documents_ocr_from: e.target.value.trim() })} /></label>
          <label>until <input aria-label="OCR runs until" placeholder="06:00" size={6} value={draft.documents_ocr_to || ""} disabled={!mine}
            onChange={(e) => setDraft({ ...draft, documents_ocr_to: e.target.value.trim() })} /></label>
          {mine && <button disabled={!changedWindow || !draft.documents_ocr_from || !draft.documents_ocr_to}
            onClick={() => save({ documents_ocr_from: draft.documents_ocr_from, documents_ocr_to: draft.documents_ocr_to })}>
            Save the window</button>}
        </div>
      )}
      {msg && <p className="status">{msg}</p>}

      <h3>Progress</h3>
      {!ocr ? <p className="quiet">Reading...</p> : (
        <div className="ocr-progress">
          <p><b>{ocr.words}</b>{ocr.window ? <span className="quiet"> · window {ocr.window[0]} to {ocr.window[1]}</span> : null}</p>
          {ocr.on && ocr.state !== "off" && (
            <>
              <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={ocr.percent}
                aria-label="OCR done"><div className="meter-fill" style={{ width: `${ocr.percent}%` }} /></div>
              <table className="grid-table small">
                <tbody>
                  <tr><th>Documents asked to be read</th><td>{ocr.documents ?? "—"}</td></tr>
                  <tr><th>Pages waiting</th><td>{ocr.waiting}</td></tr>
                  <tr><th>Pages held for the window</th><td>{ocr.parked}</td></tr>
                  <tr><th>Done</th><td>{ocr.percent}% of {ocr.peak} page(s)</td></tr>
                  <tr><th>Started</th><td>{ocr.started_at ? fmtDateTime(ocr.started_at) : "—"}</td></tr>
                  <tr><th>Last looked at</th><td>{ocr.checked_at ? fmtDateTime(ocr.checked_at) : "—"}</td></tr>
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// the short form in the header, for everyone signed in, while OCR has work (D903: "a status for all users to see")
export function OcrStatus() {
  const ocr = useOcr(30000);
  if (!ocr || !ocr.on || !["running", "parked"].includes(ocr.state)) return null;
  const text = ocr.state === "parked" ? "Documents OCR: waiting for the window" : `Documents OCR: ${ocr.percent}%`;
  return (
    <span className="startup-chip ocr-status" title={`${ocr.words}${ocr.documents != null ? `; ${ocr.documents} document(s)` : ""}`}>
      <span className={`dot ${ocr.state === "parked" ? "grey" : "amber"}`} />
      {can("system.operate") ? <a href="#/admin/documents">{text}</a> : text}
    </span>
  );
}
