# Logo and branding

Release 5.7, R5.7-B1 (owner, 16 Nov 2026; agreed 16:14, 16:15 and 17 Nov 2026 13:49; D729). An organisation can make
EA Explorer's own screens look like its own: a logo, a name, a theme, and themes of its own as CSS. Only the screens:
the sign-in page, Reports, Documents, draw.io and the files EA Explorer makes (PDF, Word and PowerPoint exports, the
canvas and journey exports, the reports' title pages) keep their own look and EA Explorer's mark.

## Who

**Super Admins** change it, on **System admin › Branding**. Everyone signed in sees it. When the Super Admins allow it,
**each person may pick their own theme** from those offered, on **My profile › My look**; the organisation's is the
default.

## What

| | |
|---|---|
| **Logo** | Shown in the top bar of every screen (PNG, JPEG, WebP or SVG, up to 512 KB; about 28 pixels high) |
| **Browser tab's icon** | A small square image (up to 128 KB) |
| **Name in the top bar** | Your name for it, for example *Meridian Atlas*; EA Explorer then shows small beside it. Empty: EA Explorer |
| **Themes that ship** | Standard (light, the look until now), Dark, High contrast (for accessibility), Corporate (muted), and twelve colours: Blue, Red, Green, Teal, Purple, Orange, Rose, Indigo, Gold, Graphite, Navy, Sand |
| **Trying one** | Choosing a theme shows it at once on your screen, to see how it feels; **Save** makes it the theme (leaving without saving goes back). The same on My profile › My look |
| **Your own themes** | Download any theme as a CSS file, change it, and add it back under a name; replace or remove the ones you added |

## The theme designer

On System admin › Branding, **Theme designer**: **Start from a copy of** any theme, then change it:

* the **colours**, each with a colour picker: accent (buttons, links, the selected tab), soft accent (highlights),
  text, quiet text, page background, panels, lines, good, bad, and the top bar's line;
* the **text font** and the **headings font** (fonts the computers already have: nothing is downloaded);
* the **text size** and the **corners** (from square to round).

Every change shows at once on your screen, with sample buttons, a link and a chip; nobody else sees it. **Save as a
new theme** keeps it under its name (a theme you made before can be changed and saved again); then choose it as the
organisation's theme, or let people pick it. **Stop designing** goes back, keeping nothing. What the designer saves is
an ordinary theme: it can be downloaded as CSS and changed by hand too.

## Fonts of your own

On System admin › Branding, **Fonts**: upload your organisation's font, a **WOFF2, WOFF, TrueType (.ttf) or OpenType
(.otf)** file up to 2 MB, under a **family name** (for example *Meridian Sans*). Upload its bold and italic files under
the same name, choosing the weight and style, to have those too; uploading one again replaces it. The table shows each
with a sample in the font itself.

The theme designer then offers it in its font lists, marked *(uploaded)*; a theme written by hand names it like any
other font: `font-family: "Meridian Sans", system-ui, sans-serif;`. Every screen loads the uploaded fonts from EA
Explorer itself (a theme still loads nothing from elsewhere: `@font-face` and `url(...)` stay refused). When a font is
removed, a theme that names it falls back to the next font in its list.

Your organisation needs the font's licence for use in a web application. Fonts are kept in the database
(`core.branding_fonts`, migration 0103): backups, restores, site copies and the organisation part of an application
backup carry them.

## A theme of your own, as CSS

1. On System admin › Branding, **Download CSS** of the theme nearest what you want (Standard has every colour).
2. Change the colours in `:root` (`--ink` text, `--quiet` quieter text, `--line` lines, `--bg` the page, `--card`
   panels, `--accent` links and buttons, `--accent-soft` highlights, `--ok` and `--bad`), the `font-family`, and add
   rules for corners or spacing if you like.
3. **Add a theme**: give it a name, choose the file (or paste the CSS), **Add it**; then choose it as the organisation's
   theme, or let people pick it.

A theme may hold only looks: colours, fonts, spacing and corners. Anything that loads from elsewhere or runs is refused
with the line it is on: `@import`, `url(...)`, `image-set(...)`, `@font-face` (name fonts the computers already have),
expressions and bindings, HTML, and backslash escapes. Braces, comments and quotes must close.

## Nobody is locked out

* **Standard look (if a theme is hard to read)** in each person's own menu puts the standard look on in that browser,
  until they choose again on My profile.
* A **break-glass** session always has the standard look.
* When the organisation's theme is removed, everyone has the standard look again.

## Where it is kept

In the database (`core.settings` key `branding`, `core.branding_files`, `core.branding_themes`; migration 0100), so
infrastructure backups and restores, site copies and the organisation part of an application backup carry it. The four
themes that ship are files in the API (`services/api/eax/branding_themes`). Each person's own choice is their setting
`theme`.

## API

| | |
|---|---|
| `GET /api/v1/branding` | the theme in use, whether people may pick, the name, the themes, the images set |
| `GET /api/v1/branding/logo`, `/favicon`, `/themes/<slug>.css[?download=1]` | the images and a theme's CSS |
| `PUT /api/v1/admin/branding` | `{theme, personal, product_name}` (Super Admins) |
| `POST/DELETE /api/v1/admin/branding/logo`, `/favicon` | upload (multipart `file`) or remove an image |
| `POST /api/v1/admin/branding/themes`, `DELETE …/themes/<slug>` | add or replace `{name, css[, slug]}`; remove one you added |

## To test

1. As a Super Admin, System admin › Branding: choose Blue: your screen turns blue at once; leave the page and it goes
   back; choose Dark and Save: every screen turns dark. Try High contrast and
   Corporate.
2. Upload a logo and an icon; give a name in the top bar; the top bar and the browser tab show them.
3. Download Standard's CSS, change `--accent`, add it as a theme and choose it. Try adding one with `url(...)`: refused,
   with the line.
4. Switch on *Each person may pick their own*; as another user, My profile › My look: pick another theme.
5. From the user menu, *Standard look*: the standard look in that browser; My profile: *Use the chosen theme again*.
6. Sample data: the theme *Meridian teal (sample)* is there, not chosen.
