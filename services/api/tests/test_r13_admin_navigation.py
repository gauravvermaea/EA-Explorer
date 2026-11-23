"""Release 13 (R13.1, R13.2; D898): System Admin in three levels, the same in the menu and on the page (owner,
23 Nov 2026: "Not all tab items can be reached from menu. The tab itself is cluttered. We need Sub menus, we need sub
tabs"). A group (the admin's task), its pages (the group's tabs, at most 8, instead of one strip of 37 on every page),
and a page's sub-pages (its sub-tabs), each with an address of its own and an entry in the menu. Both the menu
(menu.js) and the page (Admin.jsx) are made from one list, services/web/src/adminNav.js."""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web" / "src"


def _src(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


NAV = _src("adminNav.js")
GROUPS = re.findall(r'^  \{ key: "([a-z]+)", label: "([^"]+)", icon: "[^"]+", pages: \[', NAV, re.M)
PAGES = re.findall(r'\{ key: "([a-z-]+)", label: "([^"]+)", ok:', NAV)
SUBS = {k: re.findall(r'\["([a-z-]+)", "[^"]+"\]', subs)
        for k, subs in re.findall(r'\{ key: "([a-z-]+)", label: "[^"]+",[^{}]*?subs: \[((?:\s*\["[a-z-]+", "[^"]+"\],?)+)\s*\]', NAV)}

# the 37 System Admin pages before Release 13 (Admin.jsx's TABS): each still opens at its old address
OLD = ["wizards", "application", "system", "users", "security", "health", "alerts", "containers", "logs", "hosts", "mounts",
       "databases", "secrets", "pairings", "settings-transfer", "db-maintenance", "optimisation", "jobs", "sizing", "persist",
       "footprint", "estate", "scaling", "self-test", "backups", "restores", "disaster-recovery", "quality", "sql",
       "machine-access", "operations", "updates", "commands", "setup", "banner", "branding", "licences"]

# the pages with tabs of their own, and the file that draws them
OWN_TABS = {"users": "Users.jsx", "machine-access": "MachineAccess.jsx", "containers": "ContainerConsole.jsx",
            "estate": "Estate.jsx", "commands": "CommandCentre.jsx", "self-test": "TestRuns.jsx"}


def _group_pages(nav: str) -> dict[str, list[str]]:
    out = {}
    for i, (g, _) in enumerate(GROUPS):
        start = nav.index(f'{{ key: "{g}", label: ')
        end = nav.index(f'{{ key: "{GROUPS[i + 1][0]}", label: ') if i + 1 < len(GROUPS) else nav.index("export const ADMIN_PAGES")
        out[g] = re.findall(r'\{ key: "([a-z-]+)", label: "[^"]+", ok:', nav[start:end])
    return out


def test_seven_groups_by_the_admins_task_at_most_eight_pages_each():
    assert [label for _, label in GROUPS] == ["Settings", "People and access", "Health and monitoring", "Infrastructure",
                                               "Capacity", "Backups and recovery", "Tools"]
    for g, pages in _group_pages(NAV).items():
        assert 1 <= len(pages) <= 8, (g, pages)


def test_one_name_for_one_thing_and_every_old_address_still_opens():
    keys = [k for k, _ in PAGES]
    labels = [label for _, label in PAGES]
    assert len(keys) == len(set(keys)) and len(labels) == len(set(labels)), (keys, labels)
    assert not [k for k in OLD if k not in keys], "an old #/admin/<page> address would open nothing"
    shown = set(re.findall(r't\[0\] === "([a-z-]+)" \?', _src("Admin.jsx")))
    assert shown <= set(keys), shown - set(keys)     # every page Admin.jsx draws is in the list (and so in the menu)


def test_multi_level_tabs_as_projects_and_models_have_them():
    """Owner, 23 Nov 2026, 21:16: "I want multi level tabs like we have in Projects and model, you still land in the tab
    you selected but other tabs should also be there at the same structure as the menu": PageNav draws every group (a
    row of tabs), the group's pages (a second row) and where you are; the page's own sub-tabs are the third row; each
    group opens on the page last used in it, and each page on the sub-tab last used on it."""
    admin = _src("Admin.jsx")
    assert "const TABS = [" not in admin and "TABS.map" not in admin
    assert '<PageNav page="admin" tabs={ADMIN_PAGES.filter((p) => p.ok()).map((p) => [p.key, p.label])}' in admin
    assert "groups={ADMIN_GROUPS.map((g) => [g.key, g.label, g.icon, g.pages.map((p) => p.key)])}" in admin
    assert 'crumbs={[{ label: "System admin", href: "#/admin" }]}' in admin and 'subLabel={sub ? sub[1] : ""}' in admin
    nav = _src("PageNav.jsx")      # the same component as Projects and models
    assert 'className="tabs nav-groups"' in nav and "const groupHref = (g) => href(g.tabs.some((t) => t[0] === last[g.k])" in nav
    assert '<PageNav page="project"' in _src("Projects.jsx")
    assert 'const last = readLastTabs("admin-sub")[page];' in NAV and 'saveLastTab("admin-sub", page, sub);' in NAV


def test_every_sub_tab_has_an_address_and_a_menu_entry():
    assert set(SUBS) == set(OWN_TABS), set(SUBS) ^ set(OWN_TABS)
    # the menu lists each page's sub-pages, each at #/admin/<page>/<sub>
    assert "p.subs ? { items: p.subs.map(([k, l]) => ({ label: l, href: `#/admin/${p.key}/${k}` })) }" in NAV
    for page, file in OWN_TABS.items():
        src = _src(file)
        if f"#/admin/{page}/${{k}}" in src:                  # Users and Command centre: links, read from the address
            at = src.index('role="tablist"')
            listed = re.findall(r'\["([a-z-]+)", "[^"]+"\]', src[at:at + 300])
            assert listed == SUBS[page], (page, listed, SUBS[page])     # the same sub-pages, in the same order
        assert f'useSubTab("{page}")' in src, file         # every page: kept in the address and remembered
        assert 'import { useSubTab } from "./adminNav";' in src, file


def test_sub_tabs_look_the_same_on_every_page():
    for file in OWN_TABS.values():
        assert 'className="tabs sub" role="tablist"' in _src(file), file


def test_a_sub_page_address_opens_its_tab_and_survives_a_reload():
    """useSubTab reads #/admin/<page>/<sub>, follows the address as it changes (back and forward), and an unknown or
    missing sub-page opens the first; choosing a tab writes the address (keeping its ?query)."""
    assert "new RegExp(`^#/admin/${page}/([a-z0-9-]+)`)" in NAV
    assert 'window.addEventListener("hashchange", on)' in NAV and 'window.removeEventListener("hashchange", on)' in NAV
    assert "if (keys.includes(s)) return s;" in NAV and "return !s && keys.includes(last) ? last : first;" in NAV
    assert "const to = `#/admin/${page}/${k}${q ? `?${q}` : \"\"}`;" in NAV
    # Machine access: Every credential and Service accounts only for who manages every credential, else My credentials
    assert 'const view = !all && (asked === "all" || asked === "service-accounts") ? "mine" : asked;' in _src("MachineAccess.jsx")
    # Self-test: #/admin/self-test/watch[/<run>] (eax test watch --browser) still opens on Run, with the watch
    assert "#\\/admin\\/self-test\\/watch" in _src("TestRuns.jsx") and '["run", "Run"]' in _src("TestRuns.jsx")


def test_the_menu_keeps_who_sees_what():
    """The menu showed Health, Data quality and Optimisation to IT and Super Admins only (they were under Running); the
    page lets others open them, as before."""
    for k in ("health", "quality", "optimisation"):
        assert re.search(rf'\{{ key: "{k}", label: "[^"]+", ok: any, menu: ops,', NAV), k
    assert "ok: p.menu || p.ok," in NAV


def test_a_browser_journey_walks_the_three_levels():
    """The full test clicks through it (the smoke test's page sweep opens every page and sub-page in the menu)."""
    from eax.testing.ui_flows import JOURNEYS
    j = next(x for x in JOURNEYS if x["name"].startswith("system admin navigation:"))
    opened = [s["open"] for s in j["steps"] if "open" in s]
    assert "#/admin/self-test/summary" in opened and "#/admin/health" in opened        # a sub-page, and an old address
    assert {"remember": "sub", "url": r"#/admin/self-test/(history)"} in j["steps"]   # a sub-tab writes its address
