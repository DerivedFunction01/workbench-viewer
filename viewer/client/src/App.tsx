// The shell — rail + top bar on the 1600px canvas
// (ui-context §Layout), project switcher fed by the live
// /projects sweep, section nav with live count badges, and
// the ONE Settings nav entry. Appearance controls live on
// the Settings route ONLY (repo-home spec §3, the owner's
// ruling): no toggles, no gear menus in this chrome.
//
// Routing is hash-based (lib/routing): #/ is project select,
// #/p/<slug>/<section>[/<item>] the per-project sections,
// #/board the cross-project board, #/settings Settings.
// Every section's queries are scoped by the selected
// project; switching project re-scopes them all.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, type BoardPayload, type MockupsFeed, type ProjectSummary } from "./lib/api";
import { formatUptime } from "./lib/format";
import { sectionLabel } from "./lib/labels";
import type { Appearance } from "./lib/preferences";
import { applyAppearance, loadAppearance, saveAppearance } from "./lib/preferences";
import {
  boardAllHref,
  homeHref,
  parseRoute,
  type Route,
  type SectionId,
  sectionHref,
  settingsHref,
} from "./lib/routing";
import { BoardSection } from "./sections/Board";
import { MockupsSection } from "./sections/Mockups";
import { PlansSection } from "./sections/Plans";
import { SettingsSection } from "./sections/Settings";
import { TodosSection } from "./sections/Todos";

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

const badgeStyle: React.CSSProperties = {
  background: "var(--wb-surface-sunken)",
  borderRadius: "var(--wb-radius-pill)",
  padding: "0 var(--wb-space-8)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  color: "var(--wb-content-secondary)",
};

function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

function projectStatus(project: ProjectSummary): { word: string; degraded: boolean } {
  const anySection = project.sections.mockups || project.sections.todos || project.sections.plans;
  if (anySection) return { word: "ok", degraded: false };
  if (project.sections.registry_declared || project.sections.plans_declared) {
    return { word: "manifest only", degraded: false };
  }
  return { word: "manifest only", degraded: false };
}

export function App() {
  const route = useHashRoute();
  const [appearance, setAppearance] = useState<Appearance>(() => loadAppearance());

  useEffect(() => {
    applyAppearance(appearance);
  }, [appearance]);

  const changeAppearance = (next: Appearance) => {
    setAppearance(next);
    saveAppearance(next);
    applyAppearance(next);
  };

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects({}),
    refetchInterval: 30000,
  });
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth({}),
    refetchInterval: 30000,
  });
  const boardQuery = useQuery({
    queryKey: ["board"],
    queryFn: () => api.getBoard({}),
  });
  const configQuery = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig({}),
  });
  const editingOn = configQuery.data?.payload?.config.file_editing_enabled === true;

  const projects = useMemo<ProjectSummary[]>(
    () => projectsQuery.data?.payload?.projects ?? [],
    [projectsQuery.data],
  );
  const health = healthQuery.data?.payload ?? null;
  const serverOk = healthQuery.data?.status === 200 && health?.ok === true;
  const board = boardQuery.data?.payload as unknown as BoardPayload | null;

  const routeSlugValue = route.view === "section" ? route.slug : null;
  const selected = routeSlugValue
    ? (projects.find((project) => project.slug === routeSlugValue) ?? null)
    : null;

  const triageQuery = useQuery({
    queryKey: ["mockups", selected?.slug],
    queryFn: () => api.getMockups({ slug: selected?.slug ?? "" }),
    enabled: selected != null && selected.sections.mockups,
  });
  const triageCount =
    (triageQuery.data?.payload as unknown as MockupsFeed | null)?.triage.length ?? null;
  const doingCount =
    board != null
      ? (board.todos.doing ?? []).length +
        (board.plans.doing ?? []).length +
        board.review_queue.length
      : null;

  const breadcrumb = (() => {
    if (route.view === "settings") return "Settings";
    if (route.view === "board-all") return "Board · all projects";
    if (route.view === "section") {
      const name = selected?.name ?? route.slug;
      const section = sectionLabel(route.section);
      return route.item ? `${name} / ${section} / ${route.item}` : `${name} / ${section}`;
    }
    return "Projects";
  })();

  const navBadge = (section: SectionId): number | null => {
    if (section === "mockups") return triageCount;
    if (section === "board") return doingCount;
    return null;
  };

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "var(--wb-surface-canvas)",
        color: "var(--wb-content-primary)",
        fontFamily: "var(--wb-font-ui)",
      }}
    >
      <nav
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
              {projects.map((project) => {
                const status = projectStatus(project);
                const active = routeSlugValue === project.slug;
                return (
                  <li key={`${project.slug}:${project.root}`}>
                    <a
                      href={sectionHref(
                        project.slug,
                        project.sections.mockups
                          ? "mockups"
                          : project.sections.plans
                            ? "plans"
                            : "todos",
                      )}
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
              {(["mockups", "plans", "todos", "board"] as SectionId[]).map((section) => {
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
              })}
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

      <div style={{ flex: 1, minWidth: 0 }}>
        <header
          style={{
            height: "48px",
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-16)",
            padding: "0 var(--wb-page-padding)",
            borderBottom: "1px solid var(--wb-border-default)",
            background: "var(--wb-surface-1)",
          }}
        >
          <a
            href={homeHref()}
            style={{
              color: "var(--wb-content-primary)",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Workbench Viewer
          </a>
          <span style={{ color: "var(--wb-content-secondary)" }}>{breadcrumb}</span>
        </header>

        <main
          style={{
            maxWidth: "1600px",
            margin: "0 auto",
            padding: "var(--wb-page-padding)",
          }}
        >
          {route.view === "settings" ? (
            <SettingsSection appearance={appearance} onChange={changeAppearance} />
          ) : route.view === "board-all" ? (
            <BoardSection slug={null} projectName={null} />
          ) : route.view === "section" ? (
            selected == null && !projectsQuery.isPending ? (
              <p style={{ color: "var(--wb-content-secondary)" }}>
                Project <span className="mono">{route.slug}</span> is not in the current sweep.{" "}
                <a href={homeHref()} style={{ color: "var(--wb-accent)" }}>
                  Back to projects
                </a>
              </p>
            ) : route.section === "mockups" ? (
              <MockupsSection slug={route.slug} projectName={selected?.name ?? route.slug} />
            ) : route.section === "plans" ? (
              <PlansSection
                slug={route.slug}
                projectName={selected?.name ?? route.slug}
                item={route.item}
              />
            ) : route.section === "todos" ? (
              <TodosSection slug={route.slug} projectName={selected?.name ?? route.slug} />
            ) : (
              <BoardSection slug={route.slug} projectName={selected?.name ?? route.slug} />
            )
          ) : (
            <HomeView projects={projects} loading={projectsQuery.isPending} />
          )}
        </main>
      </div>
    </div>
  );
}

function HomeView({ projects, loading }: { projects: ProjectSummary[]; loading: boolean }) {
  return (
    <section>
      <h1
        style={{
          fontSize: "var(--wb-font-size-xl)",
          lineHeight: "var(--wb-line-height-xl)",
          fontWeight: 600,
          letterSpacing: "-0.011em",
          margin: "0 0 var(--wb-space-16)",
        }}
      >
        Projects
      </h1>
      {loading ? (
        <p style={{ color: "var(--wb-content-muted)" }}>Loading projects…</p>
      ) : projects.length === 0 ? (
        <p style={{ color: "var(--wb-content-secondary)" }}>
          No projects in the sweep — a project joins by carrying a workbench.yaml manifest.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {projects.map((project) => (
            <li
              key={`${project.slug}:${project.root}`}
              style={{ borderBottom: "1px solid var(--wb-border-default)" }}
            >
              <a
                href={sectionHref(
                  project.slug,
                  project.sections.mockups ? "mockups" : project.sections.plans ? "plans" : "todos",
                )}
                style={{
                  display: "flex",
                  gap: "var(--wb-space-12)",
                  alignItems: "baseline",
                  padding: "var(--wb-space-12) 0",
                  color: "var(--wb-content-primary)",
                  textDecoration: "none",
                }}
              >
                <span style={{ fontWeight: 600 }}>{project.name}</span>
                <span className="mono" style={{ color: "var(--wb-content-muted)" }}>
                  {project.slug}
                </span>
                <span style={{ color: "var(--wb-content-secondary)" }}>
                  {project.sections.mockups ? "Mockups " : ""}
                  {project.sections.plans ? "Plans " : ""}
                  {project.sections.todos ? "Todos" : ""}
                  {!project.sections.mockups && !project.sections.plans && !project.sections.todos
                    ? "Manifest only — no sections set up"
                    : ""}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
