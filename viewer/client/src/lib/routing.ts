// Hash routing — the route table (repo-home spec §2, as
// amended for this build):
//
//   #/                          workspace home (repo-home §4)
//   #/settings                  Settings (app-level)
//   #/inbox                     cross-project message inbox
//   #/p/<slug>/overview         per-project Overview (repo-home
//                               §4) — the FIRST per-project tab,
//                               ahead of the viewer's sections
//   #/p/<slug>/mockups          per-project sections…
//   #/p/<slug>/mockups/<id>     …with an optional item segment
//   #/p/<slug>/plans[/<path>]   (the plans item is a file path
//   #/p/<slug>/todos             and may itself contain slashes)
//   #/p/<slug>/board
//   #/board                     the cross-project board
//
// Unknown routes land on the default view, never a blank
// (ui-context). Parsing is pure so App stays declarative.

export type SectionId = "overview" | "mockups" | "artifacts" | "plans" | "todos" | "board";

export const SECTION_IDS: SectionId[] = [
  "overview",
  "mockups",
  "artifacts",
  "plans",
  "todos",
  "board",
];

export type Route =
  | { view: "home" }
  | { view: "settings" }
  | { view: "inbox" }
  | { view: "section"; slug: string; section: SectionId; item: string | null }
  | { view: "board-all" };

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  const parts = raw.split("/").filter((part) => part.length > 0);
  if (parts.length === 0) return { view: "home" };
  if (parts[0] === "settings" && parts.length === 1) return { view: "settings" };
  if (parts[0] === "inbox" && parts.length === 1) return { view: "inbox" };
  if (parts[0] === "board" && parts.length === 1) return { view: "board-all" };
  if (parts[0] === "p" && parts.length >= 3) {
    const slug = decodeURIComponent(parts[1] ?? "");
    const section = parts[2] as SectionId;
    if (slug && SECTION_IDS.includes(section)) {
      const item = parts.length > 3 ? parts.slice(3).map(decodeURIComponent).join("/") : null;
      return { view: "section", slug, section, item };
    }
  }
  return { view: "home" };
}

export function homeHref(): string {
  return "#/";
}

export function settingsHref(): string {
  return "#/settings";
}

export function boardAllHref(): string {
  return "#/board";
}

export function inboxHref(): string {
  return "#/inbox";
}

export function sectionHref(slug: string, section: SectionId, item?: string | null): string {
  const base = `#/p/${encodeURIComponent(slug)}/${section}`;
  return item ? `${base}/${item.split("/").map(encodeURIComponent).join("/")}` : base;
}

/** The project a route is scoped to, when it has one. */
export function routeSlug(route: Route): string | null {
  return route.view === "section" ? route.slug : null;
}
