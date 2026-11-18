// EA Explorer's own documentation, for everyone signed in (owner, 10 Nov 2026, D550): the documents of the version
// that runs, from the user menu's Documentation link.
//   #/documentation              every document, grouped, with a search across them all
//   #/documentation/<key>        one document, rendered (the API escapes everything first: nothing in a document runs)
//   #/documentation?guides=1     the printed guides only (Documentation › Printed guides, D785)
// The printed guides (the owner, 18 Nov 2026, 21:00: "I want them to be part of website documentation", D785): the 24
// PDFs made by eax site pdfs, served with the website at /site/<version>/manuals/, listed in its manuals.json.
// The same documents are in the Enterprise library, folder "EA Explorer documentation" (refreshed at every start).
// Every document and every printed guide is a tile, grouped (owner, 18 Nov 2026, 21:24: "can docs be in tiles").
import { useEffect, useRef, useState } from "react";
import { apiDownload, apiFetch } from "./auth";
import { useApi } from "./ModelViews";

export default function DocumentationPage({ route }) {
  const m = /^#\/documentation\/([^?]+)(?:\?at=(.*))?/.exec(route);
  if (m) return <DocumentPage key={m[1]} docKey={decodeURIComponent(m[1])} at={m[2] ? decodeURIComponent(m[2]) : ""} />;
  return <DocumentList />;
}

function DocumentList() {
  const { data, error } = useApi("/api/v1/documentation");
  const [q, setQ] = useState("");
  const [found, setFound] = useState(null);
  useEffect(() => {
    if (q.trim().length < 2) { setFound(null); return undefined; }
    const t = setTimeout(() => {
      apiFetch(`/api/v1/documentation/search?q=${encodeURIComponent(q.trim())}`).then((r) => setFound(r.results)).catch(() => setFound([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  if (error) return <p className="status error">{error}</p>;
  if (!data) return <p><span className="spinner" aria-hidden="true" /> Loading the documentation…</p>;
  // ?group=<name> (the top menu's Documentation › Release notes, D586): that group only
  const only = decodeURIComponent((/[?&]group=([^&]+)/.exec(window.location.hash) || [])[1] || "");
  // ?guides=1 (Documentation › Printed guides, D785): the printed guides only
  const guidesOnly = /[?&]guides=1/.test(window.location.hash);
  const groups = guidesOnly ? [] : data.groups.filter((g) => data.documents.some((d) => d.group === g) && (!only || g === only));
  if (guidesOnly) return <section className="docs-page"><PrintedGuides version={data.version} /></section>;
  return (
    <section className="docs-page">
      <h1>Documentation for EA Explorer {data.version}</h1>
      <p className="quiet">
        Every document that ships with this version: how to use EA Explorer, run it, the command line, and how it was designed.
        The same documents are in the <a href="#/enterprise-library">Enterprise library</a>, folder <em>EA Explorer documentation</em>.
      </p>
      <div className="toolbar docs-search">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search all documents"
          aria-label="Search all documents" autoFocus />
        {found && <span className="quiet">{found.length} document{found.length === 1 ? "" : "s"} found</span>}
      </div>
      {!only && !found && <PrintedGuides version={data.version} />}
      {found ? (
        found.length ? (
          <ul className="docs-found">
            {found.map((d) => (
              <li key={d.key}>
                <a href={`#/documentation/${encodeURIComponent(d.key)}`}><strong>{d.title}</strong></a> <span className="quiet small">· {d.group}</span>
                <div className="small quiet">…{d.snippet}…</div>
              </li>
            ))}
          </ul>
        ) : <p className="status">No document holds every word of “{q}”.</p>
      ) : (
        <div className="docs-tiles">
          {groups.map((g) => (
            <section key={g} className="docs-group-tiles">
              <h2>{g}</h2>
              <div className="grid">
                {data.documents.filter((d) => d.group === g).map((d) => (
                  <a key={d.key} className="tile" href={`#/documentation/${encodeURIComponent(d.key)}`}>
                    <h3>{d.title}</h3>
                    {d.summary && <p>{d.summary}</p>}
                  </a>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

// The 24 printed guides as PDFs to download (D785), as tiles like every document here (owner, 18 Nov 2026, 21:24: "can
// docs be in tiles"), from the website's own copy: /site/<version>/manuals/manuals.json.
// The website is plain files everyone may open, so this needs no API.
export function PrintedGuides({ version }) {
  const [guides, setGuides] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let on = true;
    fetch(`/site/${encodeURIComponent(version)}/manuals/manuals.json`, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => { if (on) setGuides(d.guides || []); })
      .catch(() => { if (on) setFailed(true); });
    return () => { on = false; };
  }, [version]);
  const base = `/site/${encodeURIComponent(version)}/manuals/`;
  return (
    <section className="docs-group-tiles printed-guides">
      <h2>Printed guides</h2>
      <p className="quiet">The 24 guides to print and keep, as PDF: each with a cover, what it is for, who it is for, a table of
        contents and a picture of every screen. The same are on the <a href={`/site/${encodeURIComponent(version)}/printed-guides/index.html`}
        target="_blank" rel="noopener noreferrer">website ↗</a> and in the repository's <code>documents</code> folder.</p>
      {failed || (guides && !guides.length) ? (
        <p className="status">The printed guides are not in this installation yet: on the machine, <code>eax site pdfs</code> makes them,
          then <code>eax up</code> serves them.</p>
      ) : !guides ? <p><span className="spinner" aria-hidden="true" /> Reading the printed guides…</p> : (
        <div className="grid">
          {guides.map((g) => (
            <a key={g.id} className="tile live" href={base + encodeURIComponent(g.file)} download title={`Download: ${g.title}`}>
              <h3>{g.id.split("-")[0]}. {g.title}</h3>
              <p>For {g.audience}.</p>
              <p className="small">⬇ PDF, {(g.bytes / 1048576).toFixed(1)} MB</p>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function DocumentPage({ docKey, at }) {
  const { data, error } = useApi(`/api/v1/documentation/${encodeURIComponent(docKey)}`);
  const body = useRef(null);
  useEffect(() => {
    if (!data || !body.current) return;
    const el = at ? body.current.querySelector(`#doc-${CSS.escape(at.toLowerCase())}`) : null;
    if (el) el.scrollIntoView(); else window.scrollTo(0, 0);
  }, [data, at]);
  if (error) return <section><p><a href="#/documentation">Documentation</a></p><p className="status error">{error}</p></section>;
  if (!data) return <p><span className="spinner" aria-hidden="true" /> Loading…</p>;
  const onClick = (e) => {                        // anchors within the document scroll; others are normal links
    const a = e.target.closest("a");
    const href = a && a.getAttribute("href");
    if (href && href.startsWith("#doc-")) {
      e.preventDefault();
      body.current.querySelector(`#${CSS.escape(href.slice(1))}`)?.scrollIntoView();
    }
  };
  return (
    <section className="docs-page">
      <p className="small"><a href="#/documentation">Documentation</a> › {data.group}</p>
      <div className="toolbar docs-doc-bar">
        <span className="quiet small">EA Explorer {data.version} · {data.file}</span>
        <span className="spacer" />
        <button onClick={() => apiDownload(`/api/v1/documentation/${encodeURIComponent(docKey)}/download`, data.file)}
          title="Download this document's own file">⬇ Download</button>
        {data.pdf && <button onClick={() => apiDownload(`/api/v1/documentation/${encodeURIComponent(docKey)}/pdf`, `${data.file.replace(/\.[^.]+$/, "")}.pdf`)}
          title="Download this drill as a PDF">⬇ Download PDF</button>}
        <button onClick={() => window.print()} title="Print this document, or save it as a PDF from the print dialog">Print or save as PDF</button>
      </div>
      {/* a plain-text document (the command line's help) has no heading of its own: show its title (R2.0.1) */}
      {!/<h1[\s>]/.test(data.html || "") && <h1>{data.title}</h1>}
      {/* the API built this HTML from the document escaped first, so it holds only the tags it made itself */}
      <article ref={body} className="doc-body" onClick={onClick} dangerouslySetInnerHTML={{ __html: data.html }} />
    </section>
  );
}
