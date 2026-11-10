// Hash routing — the route table (repo-home spec §2, as
// amended for this build):
//
//   #/                          workspace home (repo-home §4)
//   #/settings                  Settings (app-level)
//   #/inbox                     cross-project message inbox
//   #/projects                  the project chooser (the
//                               Project tab's target when no
//                               project is in scope)
//   #/p/<slug>/overview         per-project Overview (repo-home
//                               §4) — the FIRST per-project tab,
//                               ahead of the viewer's sections
//   #/p/<slug>/entries          per-project sections…
//   #/p/<slug>/entries/<id>     …with an optional item segment
//                               (the retired mockups/artifacts
//                               segments map here at parse time)
//   #/p/<slug>/plans[/<path>]   (the plans item is a file path
//   #/p/<slug>/todos             and may itself contain slashes)
//   #/p/<slug>/board
//   #/board                     the cross-project board
//   #/repos                     the repo census (absorption
//                               plan, step 8) — app-level,
//                               like the board
//   #/repos/<id>                one repo; the id is a
//                               workspace-relative path and
//                               may itself contain slashes
//
// Unknown routes land on the default view, never a blank
// (ui-context). Parsing is pure so App stays declarative.

export type SectionId = "overview" | "entries" | "plans" | "todos" | "board";

export const SECTION_IDS: SectionId[] = ["overview", "entries", "plans", "todos", "board"];

// The retired collection segments (the 2026-11-10
// unification): old hashes in messages and bookmarks
// land on the unified section, item segment preserved.
const RETIRED_SECTION_SEGMENTS: Record<string, SectionId> = {
  mockups: "entries",
  artifacts: "entries",
};

export type Route =
  | { view: "home" }
  | { view: "settings" }
  | { view: "inbox" }
  | { view: "picker" }
  | { view: "section"; slug: string; section: SectionId; item: string | null }
  | { view: "board-all" }
  | { view: "repos"; repoId: string | null };

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  const parts = raw.split("/").filter((part) => part.length > 0);
  if (parts.length === 0) return { view: "home" };
  if (parts[0] === "settings" && parts.length === 1) return { view: "settings" };
  if (parts[0] === "inbox" && parts.length === 1) return { view: "inbox" };
  if (parts[0] === "projects" && parts.length === 1) return { view: "picker" };
  if (parts[0] === "board" && parts.length === 1) return { view: "board-all" };
  if (parts[0] === "repos") {
    const repoId = parts.length > 1 ? parts.slice(1).map(decodeURIComponent).join("/") : null;
    return { view: "repos", repoId };
  }
  if (parts[0] === "p" && parts.length >= 3) {
    const slug = decodeURIComponent(parts[1] ?? "");
    const section = (RETIRED_SECTION_SEGMENTS[parts[2] ?? ""] ?? parts[2]) as SectionId;
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

/** The project chooser (the Project tab's destination
 * when no project is in scope): a list, never a jump
 * into whichever project an ordering happens to put
 * first. */
export function pickerHref(): string {
  return "#/projects";
}

export function sectionHref(slug: string, section: SectionId, item?: string | null): string {
  const base = `#/p/${encodeURIComponent(slug)}/${section}`;
  return item ? `${base}/${item.split("/").map(encodeURIComponent).join("/")}` : base;
}

/** The repo census, or one repo within it (the id's
 * segments are encoded individually, like a plans item). */
export function reposHref(repoId?: string | null): string {
  if (!repoId) return "#/repos";
  return `#/repos/${repoId.split("/").map(encodeURIComponent).join("/")}`;
}

/** The project a route is scoped to, when it has one. */
export function routeSlug(route: Route): string | null {
  return route.view === "section" ? route.slug : null;
}
