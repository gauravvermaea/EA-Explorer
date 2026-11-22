// Logo and branding (R5.7-B1, D729): the look of EA Explorer's own screens. Reports, Documents, draw.io and the
// sign-in page keep their own; the files EA Explorer makes keep its mark (owner, 17 Nov 2026).
//   * the theme: the organisation's (System admin > Branding), or the person's own from those offered when the Super
//     Admins allow it (My profile > My look, kept in their own settings under "theme"); its CSS goes in one <style>
//     after the screens' own, so a theme only changes the look
//   * never locked out: a break-glass session always has the standard look, and #/my-profile?look=standard (in each
//     person's menu) puts it on in this browser until they choose again
//   * the logo and the browser tab's icon, and the product name in the top bar
import { useEffect, useState } from "react";
import { apiBlobUrl, apiBytes, apiDownload, apiFetch, apiText, isBreakGlass } from "./auth";
import ThemeDesigner from "./ThemeDesigner";

const STYLE_ID = "eax-theme";
const LOOK_KEY = "eax.look";
let state = { loaded: false, data: null, theme: "standard", mine: null, own: [], fellBack: null, logo: null, favicon: null };
// a person's own theme is chosen as own-theme.<slug> (R9.5, D827)
export const OWN = "own-theme.";
const listeners = new Set();
const set = (patch) => { state = { ...state, ...patch }; listeners.forEach((f) => f(state)); };

function rescue() {
  try { return window.localStorage.getItem(LOOK_KEY) === "standard"; } catch { return false; }
}
export function setRescue(on) {
  try { if (on) window.localStorage.setItem(LOOK_KEY, "standard"); else window.localStorage.removeItem(LOOK_KEY); } catch { /* no storage */ }
}

// the theme this person sees: standard when rescued or on break-glass; theirs when allowed and still offered;
// otherwise the organisation's
// (R9.5, D827): only the themes the Super Admins offer (data.offered), or one of the person's own when they may make them
export function themeFor(data, mine, { breakGlass = false, rescued = false, own = [] } = {}) {
  if (!data || breakGlass || rescued) return "standard";
  const every = new Set((data.themes || []).map((t) => t.slug));
  const offered = new Set(data.offered || [...every]);
  if (data.personal && mine) {
    if (mine.startsWith(OWN)) { if (data.own && own.includes(mine.slice(OWN.length))) return mine; }
    else if (offered.has(mine) && every.has(mine)) return mine;
  }
  return every.has(data.theme) ? data.theme : "standard";
}

function putStyle(css) {
  let el = document.getElementById(STYLE_ID);
  if (!css) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement("style"); el.id = STYLE_ID; document.head.appendChild(el); }
  el.textContent = css;   // text, never HTML: the API also checked it holds only looks
}

function putFavicon(url) {
  let link = document.querySelector("link[rel='icon']");
  if (!url) return;
  if (!link) { link = document.createElement("link"); link.rel = "icon"; document.head.appendChild(link); }
  link.href = url;
}

export const cssUrl = (slug) => (slug.startsWith(OWN) ? `/api/v1/branding/my-themes/${encodeURIComponent(slug.slice(OWN.length))}.css`
  : `/api/v1/branding/themes/${encodeURIComponent(slug)}.css`);

async function apply() {
  const slug = themeFor(state.data, state.mine, { breakGlass: isBreakGlass(), rescued: rescue(), own: state.own.map((t) => t.slug) });
  set({ theme: slug });
  document.documentElement.dataset.eaxTheme = slug;
  if (slug === "standard") { putStyle(""); return; }
  try { putStyle(await apiText(cssUrl(slug))); } catch { putStyle(""); }
}

// try a theme on this screen only, at once, without saving (owner, 17 Nov 2026, 15:21: "When we select a theme it should
// be immediately applied so someone can see what it feels like and save makes it permanent"); endPreview() goes back
let previewing = null;
export async function previewTheme(slug) {
  previewing = slug || null;
  if (!slug) { await apply(); return; }
  document.documentElement.dataset.eaxTheme = slug;
  if (slug === "standard") { putStyle(""); return; }
  try {
    const css = await apiText(`/api/v1/branding/themes/${encodeURIComponent(slug)}.css`);
    if (previewing === slug) putStyle(css);        // a later choice wins
  } catch { /* not readable: the look stays as it is */ }
}
// the theme designer's CSS, shown at once on this screen only (D735)
export function previewCss(css) {
  previewing = "designer";
  putStyle(css);
}
export async function endPreview() {
  if (previewing === null) return;
  previewing = null;
  await apply();
}

// the fonts Super Admins uploaded (D736): loaded from the API as bytes and added to the page's fonts, so a theme can
// name them; nothing is loaded from elsewhere
const fontsIn = new Set();
export async function loadFonts(fonts) {
  if (typeof FontFace === "undefined" || !document.fonts) return;
  await Promise.all((fonts || []).map(async (f) => {
    const key = `${f.slug}:${f.v}`;
    if (fontsIn.has(key)) return;
    try {
      const face = new FontFace(f.family, await apiBytes(`/api/v1/branding/fonts/${encodeURIComponent(f.slug)}?v=${f.v}`),
        { weight: f.weight === "bold" ? "700" : "400", style: f.style || "normal" });
      document.fonts.add(await face.load());
      fontsIn.add(key);
    } catch { /* a font that cannot be read: the theme's next font is used */ }
  }));
}

export async function loadBranding() {
  let data = null;
  try { data = await apiFetch("/api/v1/branding"); } catch { /* no API: the standard look */ }
  let mine = null;
  let own = [];
  if (data?.personal) {
    try { mine = ((await apiFetch("/api/v1/me/settings")).settings || {}).theme || null; } catch { /* none */ }
    if (data.own) { try { own = (await apiFetch("/api/v1/branding/my-themes")).themes || []; } catch { /* none */ } }
  }
  // a theme of theirs no longer offered (or their own themes switched off): the organisation's, and they are told once
  const fellBack = mine && themeFor(data, mine, { own: own.map((t) => t.slug) }) !== mine ? mine : null;
  const files = data?.files || {};
  const img = async (k) => (files[k] ? apiBlobUrl(`/api/v1/branding/${k}?v=${files[k].v}`).catch(() => null) : null);
  const [logo, favicon] = await Promise.all([img("logo"), img("favicon")]);
  set({ loaded: true, data, mine, own, fellBack, logo, favicon });
  putFavicon(favicon);
  await loadFonts(data?.fonts);
  await apply();
}

// my own theme (null: the organisation's)
export async function chooseMine(slug) {
  setRescue(false);
  await apiFetch("/api/v1/branding/my-look", { method: "PUT", body: JSON.stringify({ theme: slug || null }) });
  set({ mine: slug || null, fellBack: null });
  await apply();
}

// my own themes again (after one is kept or removed)
export async function reloadOwn() {
  let own = [];
  try { own = (await apiFetch("/api/v1/branding/my-themes")).themes || []; } catch { /* none */ }
  set({ own });
  await apply();
}

export function useBranding() {
  const [s, setS] = useState(state);
  useEffect(() => { listeners.add(setS); setS(state); return () => listeners.delete(setS); }, []);
  return s;
}

// the rescue link: #/my-profile?look=standard (from each person's menu) puts the standard look on in this browser
export function useLookFromRoute(route) {
  useEffect(() => {
    if (!/[?&]look=standard\b/.test(route)) return;
    if (!rescue()) { setRescue(true); void apply(); }
    window.history.replaceState(null, "", "#/my-profile");   // once: a reload does not put it on again
  }, [route]);
}

// the top bar's mark: the logo when one is set, then the product name (EA Explorer kept small beside it)
export function BrandMark() {
  const b = useBranding();
  const name = (b.data?.product_name || "").trim();
  return (
    <a href="#/" className={`brand${b.logo ? " with-logo" : ""}`} title={name ? `${name} (EA Explorer)` : "EA Explorer"}>
      {b.logo && <img src={b.logo} alt="" className="brand-logo" />}
      <span className="brand-name">{name || "EA Explorer"}</span>
      {name && name !== "EA Explorer" && <span className="brand-by">EA Explorer</span>}
    </a>
  );
}

// My profile > My look: the theme for me alone, when the Super Admins allow it, from those they offer (R9.5, D827); my own
// themes (made in the designer or uploaded) when they allow that too; any theme I can see downloaded as CSS to share;
// the standard look always
export function MyLook() {
  const b = useBranding();
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [trying, setTrying] = useState(undefined);     // a theme shown, not saved yet (undefined: none)
  const [up, setUp] = useState({ name: "", css: "" });
  useEffect(() => () => { void endPreview(); }, []);         // leaving unsaved: back to the theme in use
  const data = b.data;
  if (!b.loaded) return null;
  const rescued = rescue();
  const org = (data?.themes || []).find((t) => t.slug === data?.theme);
  const offered = (data?.themes || []).filter((t) => (data?.offered || []).includes(t.slug));
  const own = data?.own ? b.own : [];
  const say = (ok, text) => setMsg({ ok, text });
  const pick = (slug) => {                              // shown at once on this screen; Save keeps it
    setTrying(slug); say(true, "");
    void (slug ? apiText(cssUrl(slug)).then(previewCss).catch(() => {}) : previewTheme(themeFor(data, null, {})));
  };
  const save = async () => {
    try { previewing = null; await chooseMine(trying); setTrying(undefined); say(true, "Saved: every screen uses it now."); }
    catch (e) { say(false, e.message); }
  };
  const undo = () => { setTrying(undefined); void endPreview(); };
  const download = (slug, name) => apiDownload(`${cssUrl(slug)}?download=1`, `${name || slug}.css`).catch((e) => say(false, e.message));
  const readFile = (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (f) f.text().then((css) => setUp((u) => ({ ...u, css, name: u.name || f.name.replace(/\.css$/i, "") })));
  };
  const keep = async () => {
    try { const r = await apiFetch("/api/v1/branding/my-themes", { method: "POST", body: JSON.stringify(up) });
      setUp({ name: "", css: "" }); await reloadOwn(); say(true, `${r.name} kept as your own: choose it above to use it.`); }
    catch (e) { say(false, e.message); }
  };
  const remove = async (t) => {
    if (!window.confirm(`Remove your theme ${t.name}?`)) return;
    try { await apiFetch(`/api/v1/branding/my-themes/${encodeURIComponent(t.slug)}`, { method: "DELETE" }); await loadBranding(); say(true, "Removed."); }
    catch (e) { say(false, e.message); }
  };
  let told = false;
  try { told = !b.fellBack || window.localStorage.getItem(`eax.look.told.${b.fellBack}`) === "1";
    if (!told) window.localStorage.setItem(`eax.look.told.${b.fellBack}`, "1"); } catch { told = true; }
  return (
    <>
      <h2>My look</h2>
      {!told && <p className="status bad">The theme you chose is no longer one you may use, so your screens use the organisation's.</p>}
      {rescued && <p className="status bad">This browser shows the standard look, whatever theme is chosen.
        <button className="linkish" onClick={() => { setRescue(false); void apply(); say(true, ""); }}> Use the chosen theme again</button></p>}
      {data?.personal ? <>
        <p className="quiet">Pick the theme your screens use. The organisation's is {org?.name || "Standard (light)"}; yours is for you alone.</p>
        <div className="row-gap">
          <select aria-label="My theme" value={(trying === undefined ? b.mine : trying) || ""} onChange={(e) => pick(e.target.value || null)}>
            <option value="">The organisation's ({org?.name || "Standard (light)"})</option>
            {offered.map((t) => <option key={t.slug} value={t.slug}>{t.name}</option>)}
            {own.map((t) => <option key={t.slug} value={OWN + t.slug}>{t.name} (mine)</option>)}
          </select>
          {trying !== undefined && <>
            <button className="primary" onClick={save}>Save</button>
            <button onClick={undo}>Undo</button>
            <span className="small quiet">Shown here to try it: Save keeps it.</span></>}
        </div>
        <details className="my-themes">
          <summary>Download a theme as CSS, to share it</summary>
          <ul className="plain-list">
            {offered.map((t) => <li key={t.slug}>{t.name} <button className="small" onClick={() => download(t.slug, t.slug)}>Download CSS</button></li>)}
          </ul>
        </details>
        {data.own && <>
          <h3>My own themes</h3>
          <p className="quiet small">Yours alone: nobody else sees them. At most ten, each a CSS file of looks only (nothing that loads
            from elsewhere or runs).</p>
          {own.length ? <ul className="plain-list">
            {own.map((t) => <li key={t.slug}>{t.name} <span className="quiet small">({Math.ceil(t.size / 1024)} KB)</span>{" "}
              <button className="small" onClick={() => download(OWN + t.slug, t.slug)}>Download CSS</button>{" "}
              <button className="small" onClick={() => remove(t)}>Remove</button></li>)}
          </ul> : <p className="quiet small">None yet.</p>}
          <div className="row-gap">
            <input value={up.name} maxLength={60} placeholder="Name" aria-label="My theme's name" onChange={(e) => setUp({ ...up, name: e.target.value })} />
            <label className="button-like">Upload a theme…<input type="file" accept=".css,text/css" hidden onChange={readFile} /></label>
            <button className="primary" disabled={!up.name.trim() || !up.css} onClick={keep}>Keep it</button>
            {up.css && <span className="small quiet">{Math.ceil(up.css.length / 1024)} KB read</span>}
          </div>
          <ThemeDesigner mine themes={offered} fonts={data.fonts || []} />
        </>}
      </> : <p className="quiet">Everyone uses the organisation's theme ({org?.name || "Standard (light)"}); the Super Admins can let each
        person pick their own.</p>}
      {!rescued && <p className="small quiet">Hard to read? <a href="#/my-profile?look=standard">Use the standard look in this browser</a>.</p>}
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`}>{msg.text}</p>}
    </>
  );
}
