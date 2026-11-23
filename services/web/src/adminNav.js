// System Admin in three levels, the same in the menu and on the page (owner, 23 Nov 2026, R13.1 and R13.2, D898:
// "Not all tab items can be reached from menu. The tab itself is cluttered. We need Sub menus, we need sub tabs"):
// a group (the admin's task), its pages (the group's tabs on the page, at most 8), and a page's own sub-pages (the
// page's sub-tabs). Every page and sub-page has an address of its own (#/admin/<page>/<sub>), so the menu, a link and
// the help all open it. The menu (menu.js) and the page (Admin.jsx) are both made from this list, so they cannot
// disagree. Every old address (#/admin/<page>) still opens its page: no page key changed.
//
// A page: { key, label, ok, roles, menu?, subs?, href?, title? }
//   key     its address, #/admin/<key>
//   ok()    may this person open it (the page says who may when not); roles: who may (for that message)
//   menu()  may this person see it in the menu (default: ok); the menu has always been stricter for some pages
//   subs    its sub-pages: [key, label], each at #/admin/<page>/<key>; the first is where the page opens
//   href()  a page that is elsewhere (Jenkins): in the menu only, never a tab
import { useEffect, useState } from "react";
import { can, myInfo, roles } from "./auth";

const any = () => true;
const ops = () => can("system.operate");
const sup = () => roles().includes("super-admin");
const IT = ["it-admin", "super-admin"];
const IT_AUDIT = ["it-admin", "super-admin", "auditor"];

export const ADMIN_GROUPS = [
  { key: "settings", label: "Settings", pages: [
    { key: "application", label: "Application settings", ok: any, roles: null },
    { key: "system", label: "System settings", ok: () => ops() || can("settings.manage"), roles: IT },
    { key: "banner", label: "Banner", ok: ops, roles: IT },
    { key: "branding", label: "Branding: logo and themes", ok: () => can("settings.manage"), roles: ["super-admin"] },   // R5.7-B1
    { key: "settings-transfer", label: "Settings import and export", ok: sup, roles: ["super-admin"] },   // Release 6.7 (D755)
    { key: "licences", label: "Licences", ok: any, roles: null },
  ] },
  { key: "access", label: "People and access", pages: [
    { key: "users", label: "Users and roles", ok: () => can("users.read"), roles: ["user-admin", "super-admin"],
      subs: [["people", "People"], ["mapping", "Keycloak role mapping"]] },
    { key: "security", label: "Security", ok: ops, roles: IT_AUDIT, title: "IP allow lists, multi-factor sign-in" },   // R5.2, R5.3
    { key: "secrets", label: "Secrets: passwords, keys and certificates", ok: ops, roles: IT },   // R6-S1
    { key: "machine-access", label: "Machine access", ok: any, roles: null,
      subs: [["mine", "My credentials"], ["all", "Every credential"], ["service-accounts", "Service accounts"], ["areas", "Areas and addresses"]] },
  ] },
  { key: "health", label: "Health and monitoring", pages: [
    { key: "health", label: "Health", ok: any, menu: ops, roles: null },
    { key: "alerts", label: "Alerts", ok: ops, roles: IT_AUDIT },   // every check, the open alerts (R5.9)
    { key: "jobs", label: "Jobs", ok: ops, roles: IT },             // the job queue, stuck jobs (R5.30)
    { key: "logs", label: "Logs", ok: ops, roles: IT_AUDIT },       // every log, the web log (R5.6)
    { key: "containers", label: "Containers", ok: ops, roles: IT,
      subs: [["properties", "Properties"], ["logs", "Logs"], ["terminal", "Terminal"], ["files", "Files"]] },
    { key: "quality", label: "Data quality", ok: any, menu: ops, roles: null },
  ] },
  { key: "infrastructure", label: "Infrastructure", pages: [
    { key: "hosts", label: "Hosts", ok: ops, roles: IT },           // the Docker engine (R2.16)
    { key: "mounts", label: "Mounts", ok: ops, roles: IT },         // volumes and bind mounts (R2.17)
    { key: "databases", label: "Databases", ok: ops, roles: IT },   // where each lives (R2.50)
    { key: "db-maintenance", label: "Database maintenance", ok: ops, roles: IT_AUDIT },   // R5.12
    { key: "persist", label: "Persist", ok: ops, roles: IT },       // what survives resets (R2.26)
    { key: "scaling", label: "Scaling", ok: ops, roles: IT },
  ] },
  { key: "capacity", label: "Capacity", pages: [
    { key: "sizing", label: "Sizing", ok: ops, roles: IT_AUDIT },   // R5.19
    { key: "optimisation", label: "Optimisation", ok: any, menu: ops, roles: null },   // R5.1: a Model Admin sees theirs
    { key: "footprint", label: "Footprint", ok: ops, roles: IT },   // how much each takes (R2.22)
    { key: "estate", label: "Estate", ok: ops, roles: IT, subs: [["logical", "Logical"], ["physical", "Physical"]] },   // R2.33
  ] },
  { key: "recovery", label: "Backups and recovery", pages: [
    { key: "backups", label: "Backups", ok: ops, roles: IT },
    { key: "restores", label: "Restores", ok: ops, roles: IT },
    { key: "disaster-recovery", label: "Disaster recovery", ok: ops, roles: IT },   // R5.6-B2
    { key: "pairings", label: "Site pairings: sync and DR sync", ok: ops, roles: IT },   // Release 6.5 (D749)
  ] },
  { key: "tools", label: "Tools", pages: [
    { key: "wizards", label: "Wizards", ok: any, roles: null },
    { key: "setup", label: "Setup", ok: ops, roles: IT },   // the guides, guided (R6.6, D750)
    { key: "updates", label: "Updates", ok: ops, roles: IT },
    { key: "operations", label: "Operations", ok: ops, roles: IT },
    { key: "sql", label: "SQL", ok: ops, roles: IT },
    { key: "commands", label: "Command centre", ok: ops, roles: IT,
      subs: [["commands", "Commands"], ["console", "Console"], ["history", "History"], ["schedules", "Schedules"]] },
    { key: "self-test", label: "Self-test", ok: ops, roles: IT,
      subs: [["run", "Run"], ["summary", "Summary"], ["history", "History"], ["security", "Security"],
        ["performance", "Performance"], ["fixtures", "Test data"], ["harness", "API harness"]] },
    // owner, 18 Nov 2026, 18:26: "make it a menu item to open in admin. It will just open the jenkins URL"
    { key: "jenkins", label: "Jenkins ↗", ok: ops, roles: IT, href: () => myInfo()?.jenkins || `http://${window.location.hostname}:8088` },
  ] },
];

// every page (not Jenkins), in menu order
export const ADMIN_PAGES = ADMIN_GROUPS.flatMap((g) => g.pages.filter((p) => !p.href).map((p) => ({ ...p, group: g })));

export const adminPage = (key) => ADMIN_PAGES.find((p) => p.key === key) || ADMIN_PAGES.find((p) => p.key === "wizards");

// the System Admin menu: a group, its pages, a page's sub-pages; extra: a page's own sub-menu (the wizards)
export function adminMenu(extra = {}) {
  return ADMIN_GROUPS.map((g) => ({
    label: g.label,
    items: g.pages.map((p) => ({
      label: p.label,
      href: p.href ? p.href() : `#/admin/${p.key}`,
      ok: p.menu || p.ok,
      ...(extra[p.key] ? { items: extra[p.key]() }
        : p.subs ? { items: p.subs.map(([k, l]) => ({ label: l, href: `#/admin/${p.key}/${k}` })) } : {}),
    })),
  }));
}

// the sub-page in the address (#/admin/<page>/<sub>), or null
export function adminSub(page) {
  const m = new RegExp(`^#/admin/${page}/([a-z0-9-]+)`).exec(window.location.hash || "");
  return m ? m[1] : null;
}

// a page's sub-tab, kept in the address: [current, go(sub)]. An unknown or missing sub-page is the first (or fallback).
export function useSubTab(page, fallback) {
  const keys = (adminPage(page)?.subs || []).map(([k]) => k);
  const first = fallback || keys[0];
  const read = () => { const s = adminSub(page); return keys.includes(s) ? s : first; };
  const [sub, setSub] = useState(read);
  useEffect(() => {
    const on = () => setSub(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, [page]);   // eslint-disable-line react-hooks/exhaustive-deps
  const go = (k) => {
    const q = (window.location.hash || "").split("?")[1];
    const to = `#/admin/${page}/${k}${q ? `?${q}` : ""}`;
    if (window.location.hash !== to) window.location.hash = to;
    setSub(k);
  };
  return [sub, go];
}
