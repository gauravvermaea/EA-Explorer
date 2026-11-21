// Small text scans written out by hand instead of regular expressions SonarQube found slow on some inputs
// (javascript:S8786, D804). Each gives exactly what the regular expression it replaces gave.

// every <...> tag replaced by `by`, as .replace(/<[^>]*>/g, by) did; atLeastOne: /<[^>]+>/ (an empty <> stays);
// nbsp: every &nbsp; replaced too, as /<[^>]+>|&nbsp;/g did
export function replaceTags(s, by, { atLeastOne = false, nbsp = false } = {}) {
  let out = "", i = 0, noClose = false;
  while (i < s.length) {
    if (s[i] === "<" && !noClose) {
      const j = s.indexOf(">", i + 1);
      if (j === -1) noClose = true;                 // no > after here: no tag can start at any later < either
      else if (!(atLeastOne && j === i + 1)) { out += by; i = j + 1; continue; }
    }
    if (nbsp && s.startsWith("&nbsp;", i)) { out += by; i += 6; continue; }
    out += s[i];
    i += 1;
  }
  return out;
}

// without the - at either end, as .replace(/^-+|-+$/g, "") did
export function trimDashes(s) {
  let a = 0, b = s.length;
  while (a < b && s[a] === "-") a += 1;
  while (b > a && s[b - 1] === "-") b -= 1;
  return s.slice(a, b);
}

// without the dots at the end, as .replace(/\.+$/, "") did
export function noEndDots(s) {
  let e = s.length;
  while (e > 0 && s[e - 1] === ".") e -= 1;
  return s.slice(0, e);
}

// the name being typed at the end (a letter or _, then letters, digits, _ and .), as /[A-Za-z_][A-Za-z0-9_.]*$/ found it
export function trailingName(s) {
  let i = s.length;
  while (i > 0 && /[A-Za-z0-9_.]/.test(s[i - 1])) i -= 1;
  while (i < s.length && !/[A-Za-z_]/.test(s[i])) i += 1;
  return s.slice(i);
}

// without a closing • and the spaces around it, as .replace(/\s*•\s*$/, "") did (unchanged when it has none)
export function withoutEndBullet(s) {
  const t = s.trimEnd();
  return t.endsWith("•") ? t.slice(0, -1).trimEnd() : s;
}

// the [label](address) links of a text, as /\[([^\]\n]+)\]\(([^)\s]+)\)/g found them: {index, length, label, href}
export function markdownLinks(s) {
  const out = [];
  let stop = -1;                                   // the first ] or line break after the [ being looked at
  let from = 0;                                    // where the next [ is looked for
  for (;;) {
    const i = s.indexOf("[", from);
    if (i === -1) return out;
    from = i + 1;
    if (stop <= i) {
      const close = s.indexOf("]", i + 1), nl = s.indexOf("\n", i + 1);
      stop = close === -1 ? (nl === -1 ? s.length : nl) : (nl === -1 ? close : Math.min(close, nl));
    }
    if (stop === i + 1 || s[stop] !== "]" || s[stop + 1] !== "(") continue;
    let e = stop + 2;
    while (e < s.length && s[e] !== ")" && !/\s/.test(s[e])) e += 1;
    if (e === stop + 2 || s[e] !== ")") continue;
    out.push({ index: i, length: e + 1 - i, label: s.slice(i + 1, stop), href: s.slice(stop + 2, e) });
    from = e + 1;                                  // the next link starts after this one
  }
}

// one key form for a piece of screen text: spaces collapsed, then a closing ":" or "…" (and the spaces before it) or
// "..." taken off, as .replace(/\s+/g, " ").trim().replace(/(\s*[:…]|\.\.\.)$/, "").trim() did (the help's norm)
export function textKey(t) {
  const s = String(t || "").replace(/\s+/g, " ").trim();
  if (s.endsWith(":") || s.endsWith("…")) return s.slice(0, -1).trim();
  return (s.endsWith("...") ? s.slice(0, -3) : s).trim();
}

// https://, then no spaces, with a / that is neither first nor last after it, as /^https:\/\/\S+\/\S+$/ tested
export function isGitAddress(r) {
  return /^https:\/\/\S+$/.test(r) && r.slice(9, -1).includes("/");
}
