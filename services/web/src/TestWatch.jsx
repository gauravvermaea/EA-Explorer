// Watching a self-test as it happens (R3.2; owner, 13 Nov 2026: "When running test can we have the name of test being
// executed with what it is testing. There should also be a window where someone can watch what is happening"; decided:
// it watches and can Stop the whole run, no per-step controls). Self-test › a run going on › Watch, and
// `eax test watch` in a terminal. Every two seconds it asks GET /api/v1/admin/tests/<run>/live for what is new: the step
// running now (what it checks), the counts and how many are left, each check as it is recorded, every failure with its
// reason, and the run's log lines.
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "./auth";
import { Modal } from "./ModelOps";
import { Phases } from "./TestPhases";

// The Live browser panel (R5.20; owner, 14 Nov 2026: "view how testing is going I mean actual clicks etc in chromium";
// "stream to start only on demand"): nothing is captured until it is opened; while open it asks every LARGE_MS for the
// browser shown large (its newest frame only: a slow connection skips frames) and the tiles' small stills; closing it
// (or leaving the page) stops the asking and the runner stops capturing within 30 seconds. A run started to be watched
// can be paused after each step: Step takes one, Continue lets it go.
const LARGE_MS = 300, TILES_MS = 2000;

// Full screen (R5.5.2; owner, 15 Nov 2026: "when we watch live UI of testing can we make it full screen"; "A thin
// bar"): the picture fills the screen (the browser's own full screen; Esc leaves it), scaled to fit; a thin bar at the
// top with the step, Pause, Step and Continue (slow motion) and Exit full screen, hidden after a few seconds and back
// when the mouse moves. Nothing more is captured than in the panel: the same picture.
const BAR_HIDE_MS = 3000;

export function LiveBrowser({ runId, open }) {
  const [large, setLarge] = useState("");
  const [d, setD] = useState(null);
  const [frame, setFrame] = useState(null);
  const [err, setErr] = useState("");
  const seq = useRef(0);
  const stage = useRef(null);
  const [full, setFull] = useState(false);
  const [bar, setBar] = useState(true);
  const hide = useRef(null);
  useEffect(() => {
    const changed = () => setFull(document.fullscreenElement === stage.current && !!stage.current);
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);
  useEffect(() => {
    if (!full) return undefined;
    const show = () => {
      setBar(true);
      clearTimeout(hide.current);
      hide.current = setTimeout(() => setBar(false), BAR_HIDE_MS);
    };
    show();
    const el = stage.current;
    el?.addEventListener("mousemove", show);
    return () => { el?.removeEventListener("mousemove", show); clearTimeout(hide.current); };
  }, [full]);
  const enterFull = () => { stage.current?.requestFullscreen?.().catch((e) => setErr(`Full screen: ${e.message}`)); };
  const exitFull = () => { if (document.fullscreenElement) document.exitFullscreen?.(); };
  useEffect(() => {
    if (!open) return undefined;
    let alive = true, timer;
    const ask = async () => {
      try {
        const x = await apiFetch(`/api/v1/admin/tests/${runId}/live-browser?large=${encodeURIComponent(large)}&since=${seq.current}`);
        if (!alive) return;
        setD(x); setErr("");
        if (!large && x.tiles.length) setLarge(x.tiles[0].browser);
        if (x.frame) { seq.current = x.frame.seq; setFrame(x.frame); }
        timer = setTimeout(ask, large ? LARGE_MS : TILES_MS);
      } catch (e) { if (alive) { setErr(e.message); timer = setTimeout(ask, 5000); } }
    };
    ask();
    return () => { alive = false; clearTimeout(timer); };
  }, [runId, open, large]);
  if (!open) return null;
  const control = (action) => apiFetch(`/api/v1/admin/tests/${runId}/live-browser`, { method: "POST", body: JSON.stringify({ action }) })
    .catch((e) => setErr(e.message));
  const tile = d?.tiles.find((t) => t.browser === large);
  const c = d?.controls || {};
  return (
    <div className="live-browser">
      {err && <p className="status bad small">{err}</p>}
      {!d ? <p className="small">Asking the test's browser to start showing its screen…</p>
        : !d.tiles.length ? <p className="small quiet">No browser is running now (the browser checks run after the API and database checks).
          An older test runner image cannot stream: Watch still shows the steps and the log.</p> : (<>
          <p className="small"><b>{tile?.label}</b>{tile?.step ? ` · ${tile.step}` : ""}<br /><code className="small">{tile?.url}</code></p>
          <div ref={stage} className={`live-stage${full ? " full" : ""}`}>
            {full && (
              <div className={`live-bar${bar ? "" : " hidden"}`} role="toolbar" aria-label="Live browser">
                <span className="live-bar-step" title={tile?.url || ""}><b>{tile?.label}</b>{tile?.step ? ` · ${tile.step}` : ""}</span>
                {c.slow && <>
                  <span className="small">{c.paused ? "Paused after each step" : "Running"}</span>
                  <button className="small" onClick={() => control(c.paused ? "continue" : "pause")}>{c.paused ? "Continue" : "Pause"}</button>
                  <button className="small" onClick={() => control("step")} disabled={!c.paused}>Step</button>
                </>}
                <button className="small" onClick={exitFull}>Exit full screen</button>
              </div>)}
            {frame && frame.browser === large ? <img className="live-frame" alt={`What the test's browser shows: ${tile?.step || ""}`}
              src={`data:image/jpeg;base64,${frame.jpeg}`} />
              : <p className="small quiet">Waiting for the first picture (it comes when the page changes)…</p>}
          </div>
          <p className="row-gap small">
            <button className="small" onClick={enterFull} disabled={!document.fullscreenEnabled}>Full screen</button>
            {c.slow && <>{c.paused ? <b>Paused after each step</b> : "Running"}
              <button className="small" onClick={() => control("step")}>Step</button>
              <button className="small" onClick={() => control(c.paused ? "continue" : "pause")}>{c.paused ? "Continue" : "Pause"}</button></>}
          </p>
          {d.tiles.length > 1 && <div className="live-tiles">{d.tiles.map((t) => (
            <button key={t.browser} className={`live-tile${t.browser === large ? " on" : ""}`} onClick={() => { seq.current = 0; setFrame(null); setLarge(t.browser); }}>
              {t.thumb ? <img alt="" src={`data:image/jpeg;base64,${t.thumb}`} /> : <span className="quiet small">{t.label}</span>}
              <span className="small">{t.label}</span></button>))}</div>}
        </>)}
    </div>
  );
}

const KEEP = 400;          // the newest checks and log lines kept on screen

export function mergeLive(prev, s) {
  return {
    snap: s,
    results: [...prev.results, ...(s.results || [])].slice(-KEEP),
    log: (prev.log + (s.log || "")).split("\n").slice(-KEEP).join("\n"),
    after: s.after ?? prev.after,
    from: s.log_next ?? prev.from,
  };
}

export default function TestWatch({ runId, onClose, live = false }) {
  const [st, setSt] = useState({ snap: null, results: [], log: "", after: 0, from: 0 });
  const [err, setErr] = useState("");
  const [ask, setAsk] = useState(false);
  const [msg, setMsg] = useState("");
  const [follow, setFollow] = useState(true);
  const [liveOpen, setLiveOpen] = useState(!!live);   // eax test watch --browser opens it at once (R5.20 (5))
  const pos = useRef({ after: 0, from: 0 });
  const logEnd = useRef(null);
  useEffect(() => {
    let alive = true, timer;
    const tick = async () => {
      try {
        const s = await apiFetch(`/api/v1/admin/tests/${runId}/live?after=${pos.current.after}&from=${pos.current.from}`);
        if (!alive) return;
        pos.current = { after: s.after, from: s.log_next };
        setSt((prev) => mergeLive(prev, s));
        setErr("");
        if (s.open) timer = setTimeout(tick, 2000);
      } catch (e) { if (alive) { setErr(e.message); timer = setTimeout(tick, 5000); } }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [runId]);
  useEffect(() => { if (follow) logEnd.current?.scrollIntoView?.({ block: "end" }); }, [st.log, st.results.length, follow]);
  const s = st.snap, r = s?.run, t = s?.tally || {}, p = s?.progress || {};
  const stop = async () => {
    try { const x = await apiFetch(`/api/v1/admin/tests/${runId}/stop`, { method: "POST" }); setMsg(x.message); } catch (e) { setMsg(e.message); }
    setAsk(false);
  };
  return (
    <Modal wide title={`Watching self-test ${runId}${r ? `: ${r.state}` : ""}`} onClose={onClose}
      actions={<>{s?.open && <button onClick={() => setAsk(true)} disabled={!!r?.stop_asked}>Stop the run</button>}
        <button onClick={onClose}>Close</button></>}>
      {err && <p className="status bad">{err}</p>}
      {!s && !err && <p>Loading…</p>}
      {s && <div className="test-watch" aria-live="polite">
        {s.open && <Phases phases={s.phases} />}
        <p className="test-watch-step">{s.open && <span className="spinner" aria-hidden="true" />}{" "}
          <b>{r.stop_asked ? `Stopping (asked by ${r.stop_asked})…` : r.step || (s.open ? "Starting…" : "Finished")}</b></p>
        <p className="small"><b className="ok-text">{t.passed || 0}</b> passed · <b className={t.failed ? "bad-text" : ""}>{t.failed || 0}</b> failed ·
          {" "}{t.warning || 0} warnings · {t.skipped || 0} skipped{p.total ? ` · about ${p.left} of ${p.total} left` : ""}{msg ? ` · ${msg}` : ""}</p>
        {s.failures?.length > 0 && <details open className="test-watch-failures">
          <summary className="bad-text">Failures so far ({s.failures.length})</summary>
          {s.failures.map((x) => <p key={x.id} className="small"><b>{x.suite} · {x.name}</b>: {x.detail}</p>)}</details>}
        {s.open && <details className="test-watch-live" open={liveOpen} onToggle={(e) => setLiveOpen(e.currentTarget.open)}>
          <summary>Live browser: what the test's Chromium shows, its clicks marked (nothing is captured until this is open)</summary>
          <LiveBrowser runId={runId} open={liveOpen} />
        </details>}
        <div className="test-watch-panes">
          <div className="test-watch-checks">
            <h4>Checks as they are recorded</h4>
            <ol className="small">{st.results.map((x) => (
              <li key={x.id} className={`outcome-${x.outcome}`}><span className={`rag ${x.outcome === "passed" ? "ok" : x.outcome === "failed" ? "bad" : "warn"}`}>{x.outcome}</span>
                {" "}{x.suite} · {x.name}{x.outcome !== "passed" && x.detail ? `: ${x.detail}` : ""} <span className="quiet">{x.duration_ms} ms</span></li>))}</ol>
          </div>
          <div className="test-watch-log">
            <h4>Log <label className="small quiet"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> follow</label></h4>
            <pre className="small">{st.log || "No log lines yet."}<span ref={logEnd} /></pre>
          </div>
        </div>
        <p className="quiet small">The same in a terminal: <code>eax test watch {runId}</code> (and <code>eax test stop {runId}</code>).</p>
      </div>}
      {ask && <Modal title={`Stop self-test ${runId}?`} onClose={() => setAsk(false)}
        actions={<><button onClick={() => setAsk(false)}>Keep running</button><button className="primary" onClick={stop}>Stop it</button></>}>
        <p>It ends at its next step and keeps what it has found so far.</p></Modal>}
    </Modal>
  );
}
