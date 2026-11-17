// System admin > Branding (R5.7-B1, D729; Super Admins): the logo, the browser tab's icon, the product name, the
// organisation's theme, whether each person may pick their own, and the themes: four ship, more can be added as CSS
// (download one, change it, add it back under a name). Only EA Explorer's own screens change.
import { useEffect, useState } from "react";
import { apiDownload, apiFetch, apiUpload } from "./auth";
import { endPreview, loadBranding, previewTheme, useBranding } from "./branding";
import { fmtDateTime } from "./fmt";
import ThemeDesigner from "./ThemeDesigner";

export default function BrandingAdmin() {
  const b = useBranding();
  const data = b.data;
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState({ ok: true, text: "" });
  const [add, setAdd] = useState({ name: "", css: "", replace: "" });
  useEffect(() => { if (data && !form) setForm({ theme: data.theme, personal: !!data.personal, product_name: data.product_name || "" }); }, [data, form]);
  useEffect(() => () => { endPreview(); }, []);     // leaving the page unsaved: back to the theme in use
  if (!b.loaded) return <p className="quiet">Loading…</p>;
  if (!data) return <p className="status bad">The branding could not be read.</p>;
  const say = (ok, text) => setMsg({ ok, text });
  const done = async (text) => { await loadBranding(); say(true, text); };
  const run = async (fn, text) => { try { await fn(); await done(text); } catch (e) { say(false, e.message); } };
  const changed = form && (form.theme !== data.theme || form.personal !== !!data.personal || form.product_name !== (data.product_name || ""));
  const files = data.files || {};
  const upload = (key) => (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    run(() => apiUpload(`/api/v1/admin/branding/${key}`, fd), key === "logo" ? "The logo is on every screen now." : "The browser tab's icon is set.");
  };
  const readFile = (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    f.text().then((css) => setAdd((a) => ({ ...a, css, name: a.name || f.name.replace(/\.css$/i, "") })));
  };
  const saveTheme = () => run(async () => {
    await apiFetch("/api/v1/admin/branding/themes", { method: "POST", body: JSON.stringify({ name: add.name, css: add.css, slug: add.replace || undefined }) });
    setAdd({ name: "", css: "", replace: "" });
  }, add.replace ? "The theme is replaced." : "The theme is added: choose it above to use it.");
  return (
    <section className="branding-admin">
      <p className="quiet">The look of EA Explorer's own screens: the logo, the name in the top bar and the theme. Reports, Documents,
        draw.io and the sign-in page keep their own look, and the files EA Explorer makes keep its mark. Anyone who finds a theme hard
        to read can use the standard look from their own menu (<i>Standard look</i>); a break-glass session always has it.</p>
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}

      <h2>Theme and name</h2>
      {form && <table className="facts"><tbody>
        <tr><th>The organisation's theme</th><td>
          <select aria-label="The organisation's theme" value={form.theme}
            onChange={(e) => { setForm({ ...form, theme: e.target.value }); previewTheme(e.target.value); }}>
            {data.themes.map((t) => <option key={t.slug} value={t.slug}>{t.name}{t.built_in ? "" : " (added)"}</option>)}
          </select>
          {form.theme !== data.theme && <span className="small status"> Shown on this screen only: Save makes it the organisation's theme.</span>}
          </td></tr>
        <tr><th>Each person may pick their own</th><td>
          <label className="switch-label"><input type="checkbox" checked={form.personal} onChange={(e) => setForm({ ...form, personal: e.target.checked })} />
            {" "}from the themes here, on My profile (the organisation's stays the default)</label></td></tr>
        <tr><th>Name in the top bar</th><td>
          <input value={form.product_name} maxLength={60} placeholder="EA Explorer" aria-label="Name in the top bar"
            onChange={(e) => setForm({ ...form, product_name: e.target.value })} />
          <span className="small quiet"> Empty: EA Explorer. Another name shows EA Explorer small beside it.</span></td></tr>
      </tbody></table>}
      <div className="row-gap" style={{ marginTop: 10 }}>
        <button className="primary" disabled={!changed} onClick={() => run(async () => { await apiFetch("/api/v1/admin/branding", { method: "PUT", body: JSON.stringify(form) }); await endPreview(); },
          "Saved: every screen uses it from the next page they open.")}>Save</button>
        {changed && <button onClick={() => { setForm({ theme: data.theme, personal: !!data.personal, product_name: data.product_name || "" }); endPreview(); }}>Undo my edits</button>}
      </div>

      <h2>Logo</h2>
      <div className="brand-images">
        {[["logo", "Logo in the top bar", "PNG, JPEG, WebP or SVG, up to 512 KB; about 28 pixels high on screen."],
          ["favicon", "The browser tab's icon", "A small square PNG or SVG, up to 128 KB."]].map(([k, label, hint]) => (
          <div key={k} className="brand-image">
            <h3>{label}</h3>
            <div className="brand-preview">{(k === "logo" ? b.logo : b.favicon) ? <img src={k === "logo" ? b.logo : b.favicon} alt={label} />
              : <span className="quiet small">None: {k === "logo" ? "the name only" : "the browser's own"}.</span>}</div>
            <p className="small quiet">{hint}</p>
            <div className="row-gap">
              <label className="button-like">Upload…<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden onChange={upload(k)} /></label>
              {files[k] && <button onClick={() => run(() => apiFetch(`/api/v1/admin/branding/${k}`, { method: "DELETE" }), "Removed.")}>Remove</button>}
            </div>
          </div>))}
      </div>

      <h2>Fonts</h2>
      <Fonts fonts={data.fonts || []} run={run} />

      <h2>Themes</h2>
      <p className="quiet">Sixteen ship with EA Explorer. Make your own with the theme designer below, or download one as CSS, change it and
        add it back under a name. A theme may hold only looks: nothing that loads from elsewhere (url, @import) or runs; an uploaded font
        is named by its family.</p>
      <table className="grid-table small">
        <thead><tr><th>Theme</th><th>Kind</th><th>Changed</th><th /></tr></thead>
        <tbody>
          {data.themes.map((t) => (
            <tr key={t.slug}>
              <td>{t.name}{t.slug === data.theme && <span className="chip"> in use</span>}
                {t.slug !== data.theme && <button className="linkish small" onClick={() => { setForm({ ...form, theme: t.slug }); previewTheme(t.slug); }}> try it</button>}</td>
              <td>{t.built_in ? "ships with EA Explorer" : "added"}</td>
              <td className="small">{t.built_in ? "" : `${t.set_by || ""} ${t.set_at ? fmtDateTime(t.set_at) : ""}`}</td>
              <td className="row-gap">
                <button className="small" onClick={() => apiDownload(`/api/v1/branding/themes/${t.slug}.css?download=1`, `${t.slug}.css`).catch((e) => say(false, e.message))}>Download CSS</button>
                {!t.built_in && <button className="small" onClick={() => setAdd({ name: t.name, css: "", replace: t.slug })}>Replace…</button>}
                {!t.built_in && <button className="small" onClick={() => { if (window.confirm(`Remove the theme ${t.name}?`)) run(() => apiFetch(`/api/v1/admin/branding/themes/${t.slug}`, { method: "DELETE" }), "Removed."); }}>Remove</button>}
              </td>
            </tr>))}
        </tbody>
      </table>

      <ThemeDesigner themes={data.themes} fonts={data.fonts || []} />

      <h3>{add.replace ? `Replace ${add.name}` : "Add a theme as CSS"}</h3>
      <div className="brand-add">
        <input value={add.name} maxLength={60} placeholder="Its name, for example Meridian blue" aria-label="Theme name"
          onChange={(e) => setAdd({ ...add, name: e.target.value })} />
        <label className="button-like">Choose a CSS file…<input type="file" accept=".css,text/css" hidden onChange={readFile} /></label>
        <textarea rows={8} value={add.css} placeholder=":root { --accent: #0b6e4f; }" aria-label="The theme's CSS" spellCheck={false}
          onChange={(e) => setAdd({ ...add, css: e.target.value })} />
        <div className="row-gap">
          <button className="primary" disabled={!add.name.trim() || !add.css.trim()} onClick={saveTheme}>{add.replace ? "Replace it" : "Add it"}</button>
          {(add.name || add.css) && <button onClick={() => setAdd({ name: "", css: "", replace: "" })}>Cancel</button>}
        </div>
      </div>
    </section>
  );
}

// Fonts for the themes (owner, 17 Nov 2026, 15:48: "In themes also give ability to upload a custom fonts file"; D736):
// a WOFF2, WOFF, TrueType or OpenType file under a family name, with its weight and style; every screen loads it from
// EA Explorer itself, and the theme designer offers it. The organisation needs the font's licence for this use.
function Fonts({ fonts, run }) {
  const [f, setF] = useState({ family: "", weight: "normal", style: "normal", file: null });
  const families = [...new Set(fonts.map((x) => x.family))];
  const send = () => {
    const fd = new FormData();
    fd.append("file", f.file); fd.append("family", f.family); fd.append("weight", f.weight); fd.append("style", f.style);
    run(async () => { await apiUpload("/api/v1/admin/branding/fonts", fd); setF({ family: f.family, weight: "normal", style: "normal", file: null }); },
      `${f.family} is uploaded: choose it in the theme designer.`);
  };
  return (
    <div className="brand-fonts">
      <p className="quiet small">Upload your organisation's font (WOFF2, WOFF, TrueType or OpenType, up to 2 MB), then choose it in the theme designer.
        Upload the bold and italic files under the same family name to have those too. Your organisation needs the font's licence for use in
        a web application.</p>
      {fonts.length > 0 && <table className="grid-table small">
        <thead><tr><th>Family</th><th>Weight and style</th><th>Sample</th><th>File</th><th /></tr></thead>
        <tbody>{fonts.map((x) => (
          <tr key={x.slug}>
            <td>{x.family}</td><td>{x.weight}{x.style !== "normal" ? `, ${x.style}` : ""}</td>
            <td style={{ fontFamily: `"${x.family}", sans-serif`, fontWeight: x.weight === "bold" ? 700 : 400, fontStyle: x.style }}>
              The quick brown fox: 0123456789</td>
            <td className="quiet">{x.content_type.replace("font/", "")}, {Math.round(x.size / 1024)} KB, {x.set_by}</td>
            <td><button className="small" onClick={() => { if (window.confirm(`Remove ${x.family} (${x.weight}, ${x.style})? A theme naming it uses its next font.`))
              run(() => apiFetch(`/api/v1/admin/branding/fonts/${x.slug}`, { method: "DELETE" }), "Removed."); }}>Remove</button></td>
          </tr>))}</tbody>
      </table>}
      <div className="row-gap">
        <input value={f.family} maxLength={60} list="font-families" placeholder="Family name, e.g. Meridian Sans" aria-label="Font family name"
          onChange={(e) => setF({ ...f, family: e.target.value })} />
        <datalist id="font-families">{families.map((x) => <option key={x} value={x} />)}</datalist>
        <select value={f.weight} onChange={(e) => setF({ ...f, weight: e.target.value })} aria-label="Font weight">
          <option value="normal">Regular</option><option value="bold">Bold</option></select>
        <select value={f.style} onChange={(e) => setF({ ...f, style: e.target.value })} aria-label="Font style">
          <option value="normal">Upright</option><option value="italic">Italic</option></select>
        <label className="button-like">{f.file ? f.file.name : "Choose the font file…"}
          <input type="file" accept=".woff2,.woff,.ttf,.otf,font/woff2,font/woff,font/ttf,font/otf" hidden
            onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) setF({ ...f, file, family: f.family || file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ") }); }} /></label>
        <button className="primary" disabled={!f.file || !f.family.trim()} onClick={send}>Upload the font</button>
      </div>
    </div>
  );
}
