// D804: each hand-written scan gives exactly what the regular expression it replaced gave (SonarQube S8786), on many
// generated texts. Run: node services/web/tests/text_scans.test.mjs (the API's tests run it when node is there).
import test from "node:test";
import assert from "node:assert/strict";
import { replaceTags, trimDashes, noEndDots, trailingName, withoutEndBullet, markdownLinks, textKey, isGitAddress } from "../src/textScan.js";
import { byText, groupDigits } from "../src/fmt.js";
import { braces, filledPath, pathParams } from "../src/apiPaths.js";
import { notFoundAlone, norm as routeNorm } from "../src/selfTestDriver.js";

let seed = 20261119;
const rand = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 2 ** 32);
const text = (alphabet, max = 14) => Array.from({ length: Math.floor(rand() * max) }, () => alphabet[Math.floor(rand() * alphabet.length)]).join("");
let failed = 0, checked = 0;
function same(name, alphabet, oldWay, newWay, runs = 6000) {
  for (let k = 0; k < runs; k += 1) {
    const s = text(alphabet);
    const a = JSON.stringify(oldWay(s)), b = JSON.stringify(newWay(s));
    checked += 1;
    if (a !== b) { failed += 1; console.log(`DIFFERENT ${name}: ${JSON.stringify(s)} old ${a} new ${b}`); return; }
  }
}

same("tags", ["<", ">", "a", " ", "/"], (s) => s.replace(/<[^>]*>/g, " "), (s) => replaceTags(s, " "));
same("tags, empty", ["<", ">", "a", "/"], (s) => s.replace(/<[^>]*>/g, ""), (s) => replaceTags(s, ""));
same("tags and nbsp", ["<", ">", "a", "&nbsp;", "&", "nbsp;", " "], (s) => s.replace(/<[^>]+>|&nbsp;/g, " "),
  (s) => replaceTags(s, " ", { atLeastOne: true, nbsp: true }));
same("dashes", ["-", "a", "b"], (s) => s.replace(/^-+|-+$/g, ""), trimDashes);
same("end dots", [".", "a", " "], (s) => s.replace(/\.+$/, ""), noEndDots);
same("trailing name", ["a", "Z", "_", "1", ".", " ", "(", "é"], (s) => { const m = /[A-Za-z_][A-Za-z0-9_.]*$/.exec(s); return m ? m[0] : ""; }, trailingName);
same("end bullet", ["•", " ", "\n", "a", " "], (s) => s.replace(/\s*•\s*$/, ""), withoutEndBullet);
same("links", ["[", "]", "(", ")", "a", " ", "\n", "/"], (s) => [...s.matchAll(/\[([^\]\n]+)\]\(([^)\s]+)\)/g)].map((m) => [m.index, m[0].length, m[1], m[2]]),
  (s) => markdownLinks(s).map((m) => [m.index, m.length, m.label, m.href]));
same("thousands", ["1", "2", "0", "9", "a", "_", "-", ".", "+", "e", " "], (s) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ","), (s) => groupDigits(s, ","));
same("braces", ["{", "}", "a", ":", "/"], (s) => [...s.matchAll(/\{([^}]+)\}/g)].map((m) => [m.index, m.index + m[0].length, m[1]]), (s) => braces(s));
const vals = { a: "x y", b: "", "a:a": "q" };
same("filled path", ["{", "}", "a", "b", ":", "/"], (s) => s.replace(/\{([^}]+)\}/g, (all, name) => { const v = vals[name.split(":").pop()]; return v ? encodeURIComponent(v) : all; }),
  (s) => filledPath(s, vals));
same("path params", ["{", "}", "a", ":", "/"], (s) => [...s.matchAll(/\{([^}]+)\}/g)].map((m) => m[1].split(":").pop()), pathParams);
same("help norm", ["a", " ", ":", "…", ".", "\n"], (s) => String(s || "").replace(/\s+/g, " ").trim().replace(/(\s*[:…]|\.\.\.)$/, "").trim(), textKey);
same("route", ["/", "?", "a", "#", " "], (s) => { const r = s.trim().replace(/\/+(\?|$)/, "$1"); return r || "#/"; }, routeNorm);
same("not found", ["Not found", "not FOUND", " ", "\n", "\r", " ", "x", "\t"], (s) => /^\s*Not found\s*$/im.test(s), notFoundAlone);
same("sort", ["b", "a", "B", "é", "10", "9", "", "x"], (s) => [...s].sort(), (s) => [...s].sort(byText));
same("git address", ["https://", "a", "/", " ", "x"], (s) => /^https:\/\/\S+\/\S+$/.test(s),
  isGitAddress);
same("leave the page", ["#/break-glass", "#/heartbeat", "#/sql", "x", "LOGOUT", "sign-out", "signout", "/", "a"],
  (s) => /^#\/(break-glass|heartbeat|sql)\b|logout|sign-?out/i.test(s), (s) => /(?:^#\/(break-glass|heartbeat|sql)\b)|logout|sign-?out/i.test(s));
console.log(failed ? `${failed} different (of ${checked} checked)` : `all the same (${checked} texts checked)`);
// a test in Node's own runner (SonarQube S2187: a file in the tests folder with no test in it); `node <file>` runs it
// as before and ends with an error when a scan differs
test("each hand-written scan gives what the regular expression it replaced gave", () => {
  assert.equal(failed, 0, `${failed} different (of ${checked} checked)`);
});
