// The EA Explorer website (tools/build_website.py, D776): Print or save as PDF, and the search that works offline
// (assets/search-index.js, made with the site; nothing is fetched for it, so it works from a file share or a laptop
// too). The only thing ever asked for is the footer's build (D844), over http only, and the page works without it.
(function () {
  // the version and build in the footer, like the application's (owner, 22 Nov 2026, 07:57, D844): the build is the
  // commit the site was published from, so it is filled in here, never when the site is made (before the commit):
  // on GitHub Pages from assets/build.json (written by .github/workflows/static.yml); inside EA Explorer, where there
  // is none, from the application's own public heartbeat; opened from a file, the version alone
  var sb = document.querySelector(".site-build");
  if (sb && window.fetch && location.protocol.indexOf("http") === 0) {
    var sv = sb.getAttribute("data-version");
    var sshow = function (b) {
      if (b && b.build && (!b.version || b.version === sv)) { sb.textContent = "Version " + sv + " \u00b7 build " + b.build; }
    };
    var sget = function (url) {
      return fetch(url, { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    };
    void sget((document.body.getAttribute("data-root") || "") + "assets/build.json").then(function (b) {
      if (b) { sshow(b); } else if (location.pathname.indexOf("/site/") === 0) { void sget("/api/v1/heartbeat").then(sshow); }
    });
  }
  document.querySelectorAll("button.print").forEach(function (b) {
    b.addEventListener("click", function () { window.print(); });
  });
  // Questions (the FAQ, D838): every question once; a role tab and the filter show the ones that match
  var faq = document.querySelector(".faq-page");
  if (faq) {
    document.documentElement.classList.add("js");
    var ftabs = faq.querySelectorAll(".role-tabs button"), ffilter = faq.querySelector(".filter");
    var fnone = faq.querySelector(".filter-none"), fcount = faq.querySelector(".faq-count"), role = "all";
    var fapply = function () {
      var words = (ffilter.value || "").toLowerCase().split(/\s+/).filter(Boolean), shown = 0;
      faq.querySelectorAll(".group").forEach(function (g) {
        var any = false;
        g.querySelectorAll("li[data-words]").forEach(function (li) {
          var mine = role === "all" || (" " + (li.getAttribute("data-roles") || "") + " ").indexOf(" " + role + " ") >= 0;
          var text = li.getAttribute("data-words") || "";
          var ok = mine && words.every(function (w) { return text.indexOf(w) >= 0; });
          li.hidden = !ok; if (ok) { any = true; shown++; }
        });
        g.hidden = !any;
      });
      fnone.hidden = shown > 0;
      if (fcount) { fcount.textContent = shown + (shown === 1 ? " question" : " questions"); }
    };
    var fpick = function (code) {
      role = code;
      ftabs.forEach(function (b) { b.setAttribute("aria-selected", b.getAttribute("data-tab") === code ? "true" : "false"); });
      try { history.replaceState(null, "", "#" + code); } catch (e) { /* a file opened from disk: no history */ }
      fapply();
    };
    ftabs.forEach(function (b) { b.addEventListener("click", function () { fpick(b.getAttribute("data-tab")); }); });
    ffilter.addEventListener("input", fapply);
    var fstart = (window.location.hash || "").slice(1);
    fpick(faq.querySelector('.role-tabs button[data-tab="' + fstart + '"]') ? fstart : "all");
  }

  // How do I: tabs by role and a filter over the tiles (works without them too: every role's tiles one after another)
  var howto = document.querySelector(".howto");
  if (howto) {
    document.documentElement.classList.add("js");
    var tabs = howto.querySelectorAll(".role-tabs button"), panes = howto.querySelectorAll(".role-pane");
    var filter = howto.querySelector(".filter"), none = howto.querySelector(".filter-none");
    var pick = function (code) {
      tabs.forEach(function (b) { b.setAttribute("aria-selected", b.getAttribute("data-tab") === code ? "true" : "false"); });
      panes.forEach(function (p) { p.classList.toggle("on", p.getAttribute("data-pane") === code); });
      try { history.replaceState(null, "", "#" + code); } catch (e) { /* a file opened from disk: no history */ }
      apply();
    };
    var apply = function () {
      var words = (filter.value || "").toLowerCase().split(/\s+/).filter(Boolean), shown = 0;
      howto.querySelectorAll(".role-pane.on .group").forEach(function (g) {
        var any = false;
        g.querySelectorAll("li[data-words]").forEach(function (li) {
          var text = li.getAttribute("data-words") || "";
          var ok = words.every(function (w) { return text.indexOf(w) >= 0; });
          li.hidden = !ok; if (ok) { any = true; shown++; }
        });
        g.hidden = !any;
      });
      none.hidden = shown > 0;
    };
    tabs.forEach(function (b) { b.addEventListener("click", function () { pick(b.getAttribute("data-tab")); }); });
    filter.addEventListener("input", apply);
    var start = (window.location.hash || "").slice(1);
    pick(howto.querySelector('.role-pane[data-pane="' + start + '"]') ? start : "all");
  }
  var box = document.querySelector(".search input");
  var params = new URLSearchParams(window.location.search);
  if (box && params.get("q")) box.value = params.get("q");
  var results = document.getElementById("results");
  if (!results) return;
  var q = (params.get("q") || "").trim().toLowerCase();
  if (!q) return;
  var words = q.split(/\s+/).filter(Boolean);
  var root = document.body.getAttribute("data-root") || "";
  var found = (window.EAX_SEARCH || []).map(function (p) {
    var t = p.t.toLowerCase(), s = (p.s || "").toLowerCase(), w = p.w.toLowerCase(), score = 0;
    for (var i = 0; i < words.length; i++) {
      var x = words[i];
      if (t.indexOf(x) >= 0) score += 10;
      if (s.indexOf(x) >= 0) score += 4;
      if (w.indexOf(x) >= 0) score += 1;
      else if (t.indexOf(x) < 0 && s.indexOf(x) < 0) return null;   // every word must be somewhere
    }
    return { p: p, score: score };
  }).filter(Boolean).sort(function (a, b) { return b.score - a.score; }).slice(0, 40);
  results.textContent = "";
  var head = document.createElement("p");
  head.className = "quiet";
  head.textContent = found.length ? found.length + " page" + (found.length === 1 ? "" : "s") + " for “" + q + "”" : "Nothing found for “" + q + "”.";
  results.appendChild(head);
  found.forEach(function (f) {
    var div = document.createElement("div"); div.className = "result";
    var a = document.createElement("a"); a.href = root + f.p.u; a.textContent = f.p.t;
    var p = document.createElement("p");
    var w = f.p.w, at = w.toLowerCase().indexOf(words[0]);
    p.textContent = f.p.s || (at >= 0 ? "…" + w.slice(Math.max(0, at - 60), at + 140) + "…" : w.slice(0, 180));
    div.appendChild(a); div.appendChild(p); results.appendChild(div);
  });
})();
