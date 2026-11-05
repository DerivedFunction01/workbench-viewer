// The desktop rail (contracts audit B1, 2026-11-05):
// the project switcher fed by the live sweep (§19
// grouping — a repo's linked worktrees nest under it),
// the section nav with its live count badges, and the
// workspace links over the server status line. All of
// it renders the shell status model (ShellStatus);
// App.tsx is composition only.

import { formatUptime } from "../../lib/format";
import { sectionLabel } from "../../lib/labels";
import {
  boardAllHref,
  inboxHref,
  type Route,
  reposHref,
  type SectionId,
  sectionHref,
  settingsHref,
} from "../../lib/routing";
import { badgeStyle } from "../shared";
import { projectStatus, type ShellStatus } from "./ShellStatus";

const railLinkStyle = (active: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "var(--wb-space-8)",
  minHeight: "38px",
  padding: "var(--wb-space-8) var(--wb-space-12)",
  borderRadius: "var(--wb-radius-sm)",
  borderLeft: active ? "2px solid var(--wb-accent)" : "2px solid transparent",
  background: active ? "var(--wb-surface-2)" : "transparent",
  color: "var(--wb-content-primary)",
  textDecoration: "none",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
});

export function ShellRail({ route, status }: { route: Route; status: ShellStatus }) {
  const {
    projectsQuery,
    projectGroups,
    routeSlugValue,
    selected,
    triageCount,
    artifactsTriageCount,
    doingCount,
    inboxCount,
    serverOk,
    health,
    editingOn,
  } = status;

  const navBadge = (section: SectionId): number | null => {
    if (section === "mockups") return triageCount;
    if (section === "artifacts") return artifactsTriageCount;
    if (section === "board") return doingCount;
    return null;
  };

  return (
    <nav
      data-anchor="shell/project-rail"
      aria-label="Projects and sections"
      style={{
        width: "232px",
        flexShrink: 0,
        background: "var(--wb-surface-1)",
        borderRight: "1px solid var(--wb-border-default)",
        padding: "var(--wb-space-16)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--wb-space-16)",
      }}
    >
      <div>
        <div
          style={{
            fontSize: "var(--wb-font-size-xs)",
            lineHeight: "var(--wb-line-height-xs)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--wb-content-secondary)",
            marginBottom: "var(--wb-space-8)",
          }}
        >
          Projects
        </div>
        {projectsQuery.isPending ? (
          <p style={{ color: "var(--wb-content-muted)" }}>Loading projects…</p>
        ) : projectsQuery.data?.payload == null ? (
          <p style={{ color: "var(--wb-danger)" }}>
            {projectsQuery.data?.error ?? "The companion server did not answer."}
          </p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {projectGroups.map(({ project, children }) => {
              const status = projectStatus(project);
              const active = routeSlugValue === project.slug;
              return (
                <li key={`${project.slug}:${project.root}`}>
                  <a
                    href={sectionHref(project.slug, "overview")}
                    style={railLinkStyle(active)}
                    aria-current={active ? "page" : undefined}
                  >
                    <span>{project.name}</span>
                    <span
                      role="img"
                      aria-label={`project status: ${status.word}`}
                      style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "var(--wb-radius-pill)",
                        background: status.degraded
                          ? "var(--wb-danger)"
                          : "var(--wb-status-implemented)",
                        flexShrink: 0,
                      }}
                    />
                  </a>
                  {/* §19 grouping: swept projects that are
                      this repo's linked worktrees nest
                      under it instead of listing flat. */}
                  {children.length > 0 ? (
                    <ul
                      style={{
                        listStyle: "none",
                        margin: "0 0 var(--wb-space-8) var(--wb-space-12)",
                        padding: "0 0 0 var(--wb-space-8)",
                        borderLeft: "1px solid var(--wb-border-default)",
                      }}
                    >
                      {children.map((child) => {
                        const childActive = routeSlugValue === child.slug;
                        return (
                          <li key={`${child.slug}:${child.root}`}>
                            <a
                              href={sectionHref(child.slug, "overview")}
                              style={{
                                ...railLinkStyle(childActive),
                                minHeight: "32px",
                              }}
                              aria-current={childActive ? "page" : undefined}
                            >
                              <span className="mono" style={{ fontSize: "var(--wb-font-size-xs)" }}>
                                {child.root.split("/").pop()}
                              </span>
                            </a>
                          </li>
                        );
                      })}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div>
        <div
          style={{
            fontSize: "var(--wb-font-size-xs)",
            lineHeight: "var(--wb-line-height-xs)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--wb-content-secondary)",
            marginBottom: "var(--wb-space-8)",
          }}
        >
          Sections
        </div>
        {selected ? (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {(["overview", "mockups", "artifacts", "plans", "todos", "board"] as SectionId[]).map(
              (section) => {
                const active = route.view === "section" && route.section === section;
                const badge = navBadge(section);
                return (
                  <li key={section}>
                    <a
                      href={sectionHref(selected.slug, section)}
                      style={railLinkStyle(active)}
                      aria-current={active ? "page" : undefined}
                    >
                      <span>{sectionLabel(section)}</span>
                      {badge != null && badge > 0 ? (
                        <span style={badgeStyle} className="num">
                          {badge}
                        </span>
                      ) : null}
                    </a>
                  </li>
                );
              },
            )}
          </ul>
        ) : (
          <a href={boardAllHref()} style={railLinkStyle(route.view === "board-all")}>
            <span>Board · all projects</span>
            {doingCount != null && doingCount > 0 ? (
              <span style={badgeStyle} className="num">
                {doingCount}
              </span>
            ) : null}
          </a>
        )}
      </div>

      <div style={{ marginTop: "auto" }}>
        <a
          href={reposHref()}
          style={railLinkStyle(route.view === "repos")}
          aria-current={route.view === "repos" ? "page" : undefined}
        >
          <span>Repos</span>
        </a>
        <a
          href={inboxHref()}
          style={railLinkStyle(route.view === "inbox")}
          aria-current={route.view === "inbox" ? "page" : undefined}
        >
          <span>Inbox</span>
          {inboxCount != null && inboxCount > 0 ? (
            <span style={badgeStyle} className="num">
              {inboxCount}
            </span>
          ) : null}
        </a>
        <a
          href={settingsHref()}
          style={railLinkStyle(route.view === "settings")}
          aria-current={route.view === "settings" ? "page" : undefined}
        >
          <span>Settings</span>
        </a>
        <p
          style={{
            color: "var(--wb-content-muted)",
            fontSize: "var(--wb-font-size-xs)",
            lineHeight: "var(--wb-line-height-xs)",
            margin: "var(--wb-space-12) 0 0",
          }}
        >
          <span
            role="img"
            aria-label={serverOk ? "server healthy" : "server unreachable"}
            style={{
              display: "inline-block",
              width: "8px",
              height: "8px",
              borderRadius: "var(--wb-radius-pill)",
              background: serverOk ? "var(--wb-status-implemented)" : "var(--wb-danger)",
              marginRight: "var(--wb-space-8)",
            }}
          />
          {serverOk && health
            ? `Server up · ${formatUptime((health as { uptime_s?: number }).uptime_s)} · editing ${editingOn ? "on" : "off"}`
            : "Server unreachable"}
        </p>
      </div>
    </nav>
  );
}
