// The theme designer (owner, 17 Nov 2026, 15:27: "add theme designer"; 15:28: "we should be able tp make copy of a theme
// and change colors using color picker"; "change fonts etx"; D735). Start from a copy of any theme, change its colours
// with colour pickers, its fonts, text size and corners: every change shows at once on this screen, and Save keeps it
// as a theme of your own (or replaces one you made). The CSS is made here from the choices: the copied theme's own
// CSS, then a designer block with the colours and the rules for fonts and corners. Fonts are the computers' own (a
// theme loads nothing from elsewhere, D729).
import { useEffect, useState } from "react";
import { apiFetch, apiText } from "./auth";
import { endPreview, loadBranding, previewCss } from "./branding";

export const COLOURS = [
  ["--accent", "Accent: buttons, links, the selected tab"], ["--accent-soft", "Accent, soft: highlights"],
  ["--ink", "Text"], ["--quiet", "Quiet text"], ["--bg", "Page background"], ["--card", "Panels"],
  ["--line", "Lines and borders"], ["--ok", "Good"], ["--bad", "Bad"], ["--topbar", "Top bar line"],
];
// the computers' own fonts, as stacks (nothing is downloaded)
export const FONTS = {
  "System": 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
  "Segoe UI": '"Segoe UI", Arial, sans-serif',
  "Arial": "Arial, Helvetica, sans-serif",
  "Helvetica": '"Helvetica Neue", Helvetica, Arial, sans-serif',
  "Verdana": "Verdana, Geneva, sans-serif",
  "Tahoma": "Tahoma, Verdana, sans-serif",
  "Trebuchet": '"Trebuchet MS", Arial, sans-serif',
  "Calibri": "Calibri, Carlito, Arial, sans-serif",
  "Georgia (serif)": "Georgia, Cambria, serif",
  "Cambria (serif)": 'Cambria, Georgia, "Times New Roman", serif',
  "Times (serif)": '"Times New Roman", Times, serif',
  "Monospace": 'ui-monospace, Consolas, "Courier New", monospace',
};
const MARK = "/* Theme designer */";

// the last value each colour has in a theme's CSS, and the designer's own settings when it made it
// the fonts uploaded (D736), named by their family, before the computers' own
export const withUploaded = (uploaded) => ({
  ...Object.fromEntries([...new Set((uploaded || []).map((f) => f.family))].map((fam) => [`${fam} (uploaded)`,
    `"${fam}", system-ui, -apple-system, "Segoe UI", Arial, sans-serif`])),
  ...FONTS,
});

export function readTheme(css, fonts = FONTS) {
  const out = { colours: {}, font: "System", heading: "System", size: 15, radius: 6 };
  for (const [k] of COLOURS) {
    const all = [...css.matchAll(new RegExp(`${k}\\s*:\\s*(#[0-9a-fA-F]{3,6})`, "g"))];
    if (all.length) out.colours[k] = expand(all[all.length - 1][1]);
  }
  const bar = [...css.matchAll(/\.topbar\s*{\s*border-bottom:\s*\d+px solid (#[0-9a-fA-F]{3,6})/g)];   // the top bar line, as drawn
  out.colours["--topbar"] = bar.length ? expand(bar[bar.length - 1][1]) : out.colours["--accent"] || "#1f5fb8";
  const fam = [...css.matchAll(/:root\s*{[^}]*font-family:\s*([^;}]+)/g)];
  if (fam.length) out.font = fontName(fam[fam.length - 1][1].trim(), fonts);
  const d = css.split(MARK)[1] || "";
  const h = /h1, h2, h3 { font-family: ([^;]+);/.exec(d); if (h) out.heading = fontName(h[1].trim(), fonts);
  const s = /body { font-size: (\d+)px/.exec(d); if (s) out.size = Number(s[1]);
  const r = /border-radius: (\d+)px/.exec(d); if (r) out.radius = Number(r[1]);
  return out;
}
const expand = (h) => (h.length === 4 ? `#${h[1]}${h[1]}${h[2]}${h[2]}${h[3]}${h[3]}` : h).toLowerCase();
const fontName = (stack, fonts = FONTS) => Object.keys(fonts).find((k) => fonts[k] === stack) || "System";

// the theme's CSS: the copied theme without any earlier designer block, then the designer's block
export function makeCss(base, t, fonts = FONTS) {
  const kept = base.split(MARK)[0].trimEnd();
  const vars = COLOURS.filter(([k]) => k !== "--topbar").map(([k]) => `${k}: ${t.colours[k]};`).join(" ");
  return `${kept}\n\n${MARK}\n:root { ${vars} font-family: ${fonts[t.font] || FONTS.System}; }\n`
    + `body { font-size: ${t.size}px; }\n`
    + `h1, h2, h3 { font-family: ${fonts[t.heading] || FONTS.System}; }\n`
    + `button, select, input, textarea, .tile, .domain, .chip { border-radius: ${t.radius}px; }\n`
    + `.topbar { border-bottom: 3px solid ${t.colours["--topbar"]}; }\n`
    + `.topbar .brand, .tab.on { color: ${t.colours["--accent"]}; }\n`
    + `button.primary { background: ${t.colours["--accent"]}; border-color: ${t.colours["--accent"]}; }\n`;
}

export default function ThemeDesigner({ themes, fonts: uploaded, onSaved }) {
  const fonts = withUploaded(uploaded);
  const [from, setFrom] = useState("");
  const [base, setBase] = useState("");
  const [t, setT] = useState(null);
  const [name, setName] = useState("");
  const [replace, setReplace] = useState("");
  const [msg, setMsg] = useState({ ok: true, text: "" });
  useEffect(() => () => { endPreview(); }, []);
  useEffect(() => { if (t && base) previewCss(makeCss(base, t, fonts)); }, [t, base]);   // every change shows at once

  const start = async (slug) => {
    setFrom(slug); setMsg({ ok: true, text: "" });
    if (!slug) { setT(null); setBase(""); endPreview(); return; }
    try {
      const css = await apiText(`/api/v1/branding/themes/${encodeURIComponent(slug)}.css`);
      const theme = themes.find((x) => x.slug === slug);
      setBase(css); setT(readTheme(css, fonts));
      setReplace(theme && !theme.built_in ? slug : "");
      setName(theme && !theme.built_in ? theme.name : `${theme?.name || slug} (our own)`);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  };
  const set = (patch) => setT((x) => ({ ...x, ...patch }));
  const save = async (asNew) => {
    try {
      const r = await apiFetch("/api/v1/admin/branding/themes", { method: "POST",
        body: JSON.stringify({ name, css: makeCss(base, t, fonts), slug: asNew ? undefined : replace || undefined }) });
      await endPreview(); await loadBranding();
      setMsg({ ok: true, text: `${r.name} saved: choose it as the organisation's theme above, or let people pick it.` });
      setReplace(r.slug);
      onSaved?.();
    } catch (e) { setMsg({ ok: false, text: e.message }); }
  };

  return (
    <div className="theme-designer">
      <h3>Theme designer</h3>
      <p className="quiet small">Start from a copy of any theme, then change its colours, fonts, text size and corners. Every change shows at
        once on this screen; nobody else sees it until you save it and choose it.</p>
      <div className="row-gap">
        <select value={from} onChange={(e) => start(e.target.value)} aria-label="Start from a copy of">
          <option value="">Start from a copy of…</option>
          {themes.map((x) => <option key={x.slug} value={x.slug}>{x.name}{x.built_in ? "" : " (ours)"}</option>)}
        </select>
        {t && <button onClick={() => start("")}>Stop designing</button>}
      </div>
      {t && <>
        <div className="td-grid">
          {COLOURS.map(([k, label]) => (
            <label key={k} className="td-colour">
              <input type="color" value={t.colours[k] || "#000000"} aria-label={label}
                onChange={(e) => set({ colours: { ...t.colours, [k]: e.target.value } })} />
              <span>{label}<span className="quiet small"> {t.colours[k]}</span></span>
            </label>))}
        </div>
        <div className="td-grid">
          <label>Text font <select value={t.font} onChange={(e) => set({ font: e.target.value })} aria-label="Text font">
            {Object.keys(fonts).map((f) => <option key={f} value={f} style={{ fontFamily: fonts[f] }}>{f}</option>)}</select></label>
          <label>Headings font <select value={t.heading} onChange={(e) => set({ heading: e.target.value })} aria-label="Headings font">
            {Object.keys(fonts).map((f) => <option key={f} value={f} style={{ fontFamily: fonts[f] }}>{f}</option>)}</select></label>
          <label>Text size <input type="range" min="12" max="18" value={t.size} onChange={(e) => set({ size: Number(e.target.value) })}
            aria-label="Text size" /> {t.size}px</label>
          <label>Corners <input type="range" min="0" max="16" value={t.radius} onChange={(e) => set({ radius: Number(e.target.value) })}
            aria-label="Corners" /> {t.radius}px</label>
        </div>
        <div className="td-sample" aria-hidden="true">
          <button className="primary">A primary button</button> <button>A button</button> <span className="chip">a chip</span>{" "}
          <a href="#/admin/branding">a link</a> <span className="status ok">Good</span> <span className="status bad">Bad</span>
        </div>
        <div className="row-gap">
          <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="The theme's name" aria-label="Designed theme's name" />
          {replace && <button className="primary" disabled={!name.trim()} onClick={() => save(false)}>Save changes</button>}
          <button className={replace ? "" : "primary"} disabled={!name.trim()} onClick={() => save(true)}>Save as a new theme</button>
        </div>
      </>}
      {msg.text && <p className={`status ${msg.ok ? "ok" : "bad"}`} role="status">{msg.text}</p>}
    </div>
  );
}
