// The shell — rail + top bar on the 1600px canvas
// (ui-context §Layout), project switcher fed by the live
// /projects sweep, section nav with live count badges, and
// the ONE Settings nav entry. Appearance controls live on
// the Settings route ONLY (repo-home spec §3, the owner's
// ruling): no toggles, no gear menus in this chrome.
//
// Routing is hash-based (lib/routing): #/ is the workspace
// home (repo-home §4), #/p/<slug>/<section>[/<item>] the
// per-project sections (Overview first, repo-home §2),
// #/board the cross-project board, #/inbox the message
// inbox, #/settings Settings. The rail groups swept
// projects by the repo -> worktree relation (§19): a
// project that is another repo's linked worktree nests
// under that repo instead of listing as a flat sibling.
// Every section's queries are scoped by the selected
// project; switching project re-scopes them all.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { SectionBoundary } from "./components/SectionBoundary";
import {
  api,
  type BoardPayload,
  type HomePayload,
  type MockupsFeed,
  type ProjectSummary,
} from "./lib/api";
import { formatUptime } from "./lib/format";
import { groupProjects } from "./lib/grouping";
import { sectionLabel } from "./lib/labels";
import type { Appearance } from "./lib/preferences";
import { applyAppearance, loadAppearance, saveAppearance } from "./lib/preferences";
import { useIsPhone } from "./lib/responsive";
import {
  boardAllHref,
  homeHref,
  inboxHref,
  parseRoute,
  type Route,
  type SectionId,
  sectionHref,
  settingsHref,
} from "./lib/routing";
import { resetContentScroll } from "./lib/scroll";
import { ArtifactsSection } from "./sections/Artifacts";
import { BoardSection } from "./sections/Board";
import { HomeSection } from "./sections/Home";
import { InboxSection } from "./sections/Inbox";
import { MockupsSection } from "./sections/Mockups";
import { OverviewSection } from "./sections/Overview";
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

// ----------------------------------------------------------------
// Phone chrome (mobile variant, <= the responsive seam's
// breakpoint): the approved mockup's shell — a top bar
// (back affordance + title/sub, structure per exhibit), the
// project section nav (the rail's Sections list as a
// segmented row, inside the body), and the bottom tab bar
// (◆1: Home / Project / Inbox / Settings). Routing and
// section state are the desktop ones — presentation only.
// The mockup top bar's theme toggle is NOT reproduced:
// appearance controls live on the Settings route only
// (repo-home spec §3), and the Settings tab is one tap away.
// ----------------------------------------------------------------

const tabIconProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  width: 20,
  height: 20,
} as const;

function HomeIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
    </svg>
  );
}

function ProjectIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function InboxIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.8 1.1z" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.9 2.9l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.2a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.9-2.9l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.9-2.9l.1.1a1.7 1.7 0 0 0 1.9.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 1 1.5h0a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.9 2.9l-.1.1a1.7 1.7 0 0 0-.3 1.9v0a1.7 1.7 0 0 0 1.5 1h.2a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

function BackIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

type PhoneTab = "home" | "project" | "inbox" | "settings";

function PhoneTabBar({
  active,
  projectHref,
  inboxCount,
}: {
  active: PhoneTab;
  projectHref: string;
  inboxCount: number | null;
}) {
  const tabs: { id: PhoneTab; label: string; href: string; icon: React.ReactNode }[] = [
    { id: "home", label: "Home", href: homeHref(), icon: <HomeIcon /> },
    { id: "project", label: "Project", href: projectHref, icon: <ProjectIcon /> },
    { id: "inbox", label: "Inbox", href: inboxHref(), icon: <InboxIcon /> },
    { id: "settings", label: "Settings", href: settingsHref(), icon: <SettingsIcon /> },
  ];
  return (
    <nav
      data-anchor="shell/tab-bar"
      aria-label="Primary"
      style={{
        // Viewport-anchored, outside the shell's height
        // equation entirely (the v1 dashboard's shape):
        // the bar cannot ride, shrink, or be clipped by
        // the shell whatever the shell's height does.
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 20,
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        borderTop: "1px solid var(--wb-border-default)",
        background: "var(--wb-surface-1)",
        padding:
          "var(--wb-space-4) var(--wb-space-4) calc(var(--wb-space-8) + env(safe-area-inset-bottom, 0px))",
      }}
    >
      {tabs.map((tab) => {
        const current = tab.id === active;
        return (
          <a
            key={tab.id}
            href={tab.href}
            aria-current={current ? "page" : undefined}
            style={{
              position: "relative",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "2px",
              padding: "var(--wb-space-4) var(--wb-space-4)",
              borderRadius: "var(--wb-radius-md)",
              fontSize: "11px",
              lineHeight: "14px",
              fontWeight: current ? 700 : 500,
              color: current ? "var(--wb-accent)" : "var(--wb-content-muted)",
              textDecoration: "none",
            }}
          >
            {tab.icon}
            <span style={{ whiteSpace: "nowrap" }}>{tab.label}</span>
            {tab.id === "inbox" && inboxCount != null && inboxCount > 0 ? (
              <span
                style={{
                  ...badgeStyle,
                  position: "absolute",
                  top: "2px",
                  left: "calc(50% + 2px)",
                }}
                className="num"
              >
                {inboxCount}
              </span>
            ) : null}
          </a>
        );
      })}
    </nav>
  );
}

function PhoneSectionNav({ slug, current }: { slug: string; current: SectionId }) {
  return (
    <nav
      data-anchor="shell/section-nav"
      aria-label="Project sections"
      style={{
        display: "flex",
        gap: "var(--wb-space-4)",
        background: "var(--wb-surface-2)",
        border: "1px solid var(--wb-border-default)",
        borderRadius: "var(--wb-radius-lg)",
        padding: "var(--wb-space-4)",
        marginBottom: "var(--wb-space-16)",
      }}
    >
      {(["overview", "mockups", "artifacts", "plans", "todos", "board"] as SectionId[]).map(
        (section) => {
          const isCurrent = section === current;
          return (
            <a
              key={section}
              href={sectionHref(slug, section)}
              aria-current={isCurrent ? "page" : undefined}
              style={{
                flex: "1 1 0",
                minWidth: 0,
                minHeight: "38px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "var(--wb-space-8) 2px",
                borderRadius: "var(--wb-radius-md)",
                border: isCurrent ? "1px solid var(--wb-border-default)" : "1px solid transparent",
                background: isCurrent ? "var(--wb-surface-1)" : "transparent",
                boxShadow: isCurrent ? "var(--wb-shadow-overlay)" : "none",
                color: isCurrent ? "var(--wb-content-primary)" : "var(--wb-content-secondary)",
                fontSize: "var(--wb-font-size-xs)",
                lineHeight: "var(--wb-line-height-xs)",
                fontWeight: isCurrent ? 700 : 500,
                textDecoration: "none",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {sectionLabel(section)}
            </a>
          );
        },
      )}
    </nav>
  );
}

function projectStatus(project: ProjectSummary): { word: string; degraded: boolean } {
  const anySection =
    project.sections.mockups ||
    project.sections.artifacts ||
    project.sections.todos ||
    project.sections.plans;
  if (anySection) return { word: "ok", degraded: false };
  if (project.sections.registry_declared || project.sections.plans_declared) {
    return { word: "manifest only", degraded: false };
  }
  return { word: "manifest only", degraded: false };
}

export function App() {
  const route = useHashRoute();
  const isPhone = useIsPhone();
  // Route changes reset the content scroll: the phone
  // presentation is plain document flow, and a new route
  // entered at the previous page's scroll depth is the
  // defect the old inner-scroller reset used to mask.
  // The reset targets the resolved content scroller —
  // the host container when embedded, the document when
  // served bare (lib/scroll).
  // biome-ignore lint/correctness/useExhaustiveDependencies: route is the trigger, not an input — the effect fires on every navigation and reads only the scroller
  useEffect(() => {
    resetContentScroll();
  }, [route]);
  // The phone bars are position:fixed (below), so the
  // content pads clear of them by their real heights:
  // measured here, published on the phone root as
  // --wb-phone-top-h / --wb-phone-tab-h (the CSS fallbacks
  // in <main>'s padding cover the first frame). A
  // ResizeObserver keeps them exact as the top bar's
  // sub-line comes and goes with the route and the tab
  // bar's safe-area inset resolves. The bars are found by
  // their contract anchors inside the phone root.
  const phoneShellRef = useRef<HTMLDivElement | null>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: isPhone is not read in the body; the dep tracks the ref's target, which exists only in the phone presentation — the effect must rebind when the presentation flips
  useLayoutEffect(() => {
    const shell = phoneShellRef.current;
    if (!shell) return;
    const top = shell.querySelector<HTMLElement>('[data-anchor="shell/top-bar"]');
    const tab = shell.querySelector<HTMLElement>('[data-anchor="shell/tab-bar"]');
    if (!top || !tab) return;
    const write = () => {
      shell.style.setProperty(
        "--wb-phone-top-h",
        `${Math.ceil(top.getBoundingClientRect().height)}px`,
      );
      shell.style.setProperty(
        "--wb-phone-tab-h",
        `${Math.ceil(tab.getBoundingClientRect().height)}px`,
      );
    };
    write();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(write);
    observer.observe(top);
    observer.observe(tab);
    return () => observer.disconnect();
  }, [isPhone]);
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
  const homeQuery = useQuery({
    queryKey: ["home"],
    queryFn: () => api.getHome({}),
    refetchInterval: 30000,
  });
  const homeRows = useMemo(
    () => (homeQuery.data?.payload as unknown as HomePayload | null)?.projects ?? null,
    [homeQuery.data],
  );
  const configQuery = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig({}),
  });
  const inboxQuery = useQuery({
    queryKey: ["messages", "", "sent"],
    queryFn: () => api.getMessages({ state: "sent" }),
    refetchInterval: 30000,
  });
  const inboxCount =
    (inboxQuery.data?.payload as unknown as { messages?: unknown[] } | null)?.messages?.length ??
    null;
  const editingOn = configQuery.data?.payload?.config.file_editing_enabled === true;

  const projects = useMemo<ProjectSummary[]>(
    () => projectsQuery.data?.payload?.projects ?? [],
    [projectsQuery.data],
  );
  const health = healthQuery.data?.payload ?? null;
  const projectGroups = useMemo(() => groupProjects(projects, homeRows), [projects, homeRows]);
  const serverOk = healthQuery.data?.status === 200 && health?.ok === true;
  const board = boardQuery.data?.payload as unknown as BoardPayload | null;

  const routeSlugValue = route.view === "section" ? route.slug : null;
  const selected = routeSlugValue
    ? (projects.find((project) => project.slug === routeSlugValue) ?? null)
    : null;

  const triageQuery = useQuery({
    queryKey: ["mockups", selected?.slug],
    queryFn: () => api.getMockups({ slug: selected?.slug ?? "" }),
    // biome-ignore lint/complexity/useOptionalChain: the boolean form is load-bearing — `selected?.sections.mockups` evaluates to undefined with no project selected, and React Query treats enabled: undefined as enabled (the query would fire with an empty slug and 422)
    enabled: selected != null && selected.sections.mockups,
  });
  const triageCount =
    (triageQuery.data?.payload as unknown as MockupsFeed | null)?.triage.length ?? null;
  const artifactsTriageQuery = useQuery({
    queryKey: ["artifacts", selected?.slug],
    queryFn: () => api.getArtifacts({ slug: selected?.slug ?? "" }),
    // biome-ignore lint/complexity/useOptionalChain: same as the mockups query above — undefined would read as enabled to React Query
    enabled: selected != null && selected.sections.artifacts,
  });
  const artifactsTriageCount =
    (artifactsTriageQuery.data?.payload as unknown as MockupsFeed | null)?.triage.length ?? null;
  const doingCount =
    board != null
      ? (board.todos.doing ?? []).length +
        (board.plans.doing ?? []).length +
        board.review_queue.length
      : null;

  const breadcrumb = (() => {
    if (route.view === "settings") return "Settings";
    if (route.view === "inbox") return "Inbox";
    if (route.view === "board-all") return "Board · all projects";
    if (route.view === "section") {
      const name = selected?.name ?? route.slug;
      const section = sectionLabel(route.section);
      return route.item ? `${name} / ${section} / ${route.item}` : `${name} / ${section}`;
    }
    return "Workspace";
  })();

  const navBadge = (section: SectionId): number | null => {
    if (section === "mockups") return triageCount;
    if (section === "artifacts") return artifactsTriageCount;
    if (section === "board") return doingCount;
    return null;
  };

  // The route content — identical for both presentations;
  // only the chrome around it differs.
  const content =
    route.view === "settings" ? (
      <SettingsSection appearance={appearance} onChange={changeAppearance} />
    ) : route.view === "inbox" ? (
      <InboxSection />
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
      ) : route.section === "overview" ? (
        <OverviewSection slug={route.slug} projectName={selected?.name ?? route.slug} />
      ) : route.section === "mockups" ? (
        <MockupsSection slug={route.slug} projectName={selected?.name ?? route.slug} />
      ) : route.section === "artifacts" ? (
        <ArtifactsSection
          slug={route.slug}
          projectName={selected?.name ?? route.slug}
          item={route.item}
        />
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
      <HomeSection />
    );

  // The routed content behind the error boundary
  // (components/SectionBoundary): a section exception
  // degrades to the boundary's fallback panel, never a
  // blank viewer. Keyed by the route — navigating away
  // remounts the boundary and clears a stuck fallback.
  const boundedContent = <SectionBoundary key={JSON.stringify(route)}>{content}</SectionBoundary>;

  if (isPhone) {
    // Phone shell (mobile variant): top bar + optional
    // section nav + content + bottom tab bar, one column.
    const phoneTab: PhoneTab =
      route.view === "inbox"
        ? "inbox"
        : route.view === "settings"
          ? "settings"
          : route.view === "home"
            ? "home"
            : "project";
    const firstProject = projectGroups[0]?.project ?? null;
    const projectHref =
      routeSlugValue != null
        ? sectionHref(routeSlugValue, "overview")
        : firstProject
          ? sectionHref(firstProject.slug, "overview")
          : homeHref();
    const homeRow =
      route.view === "section" ? (homeRows?.find((row) => row.slug === route.slug) ?? null) : null;
    // Top bar per the mockup's exhibits: Home is the root
    // (no back); a project view's back returns Home (◆3);
    // an open plan's back returns to its plan list.
    let backHref: string | null = null;
    let backLabel = "Back to Home";
    let title = "Workbench";
    let sub: string | null = null;
    let headerBadge: string | null = null;
    if (route.view === "inbox") {
      title = "Inbox";
    } else if (route.view === "settings") {
      title = "Settings";
    } else if (route.view === "board-all") {
      title = "Board";
      sub = "all projects";
      backHref = homeHref();
      if (board) {
        const total =
          board.review_queue.length +
          Object.values(board.todos).reduce((n, list) => n + list.length, 0) +
          Object.values(board.plans).reduce((n, list) => n + list.length, 0);
        headerBadge = `${total} cards`;
      }
    } else if (route.view === "section") {
      backHref = route.item ? sectionHref(route.slug, route.section) : homeHref();
      backLabel = route.item ? "Back to list" : "Back to Home";
      if (route.section === "board") {
        title = "Board";
        sub = route.slug;
        if (board) {
          const inScope = (project: string | undefined) => project === route.slug;
          const total =
            board.review_queue.filter((item) => inScope(item.project)).length +
            Object.values(board.todos).reduce(
              (n, list) => n + list.filter((todo) => inScope(todo.project)).length,
              0,
            ) +
            Object.values(board.plans).reduce(
              (n, list) => n + list.filter((plan) => inScope(plan.project)).length,
              0,
            );
          headerBadge = `${total} cards`;
        }
      } else if (route.section === "plans" && route.item) {
        title = "Plan";
        sub = route.slug;
      } else {
        title = selected?.name ?? route.slug;
        sub = homeRow?.git
          ? `${route.slug} · ${homeRow.git.branch ?? "detached"}${homeRow.git.head_short ? ` · ${homeRow.git.head_short}` : ""}`
          : route.slug;
      }
    }
    return (
      <div
        ref={phoneShellRef}
        style={{
          // Plain document flow (the git repo viewer's
          // shape): no fixed height, no overflow box, no
          // height custom property — the document scrolls
          // and the bars, position:fixed to the viewport,
          // float over it. Nothing here can be carried
          // away, shrunk, or clipped by a viewport metric.
          background: "var(--wb-surface-canvas)",
          color: "var(--wb-content-primary)",
          fontFamily: "var(--wb-font-ui)",
        }}
      >
        <header
          data-anchor="shell/top-bar"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 30,
            display: "flex",
            alignItems: "center",
            gap: "var(--wb-space-8)",
            padding: "var(--wb-space-12) var(--wb-space-16) var(--wb-space-8)",
            borderBottom: "1px solid var(--wb-border-default)",
            background: "var(--wb-surface-1)",
          }}
        >
          {backHref ? (
            <a
              href={backHref}
              aria-label={backLabel}
              style={{
                width: "38px",
                height: "38px",
                flexShrink: 0,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "var(--wb-radius-md)",
                border: "1px solid var(--wb-border-default)",
                background: "var(--wb-surface-2)",
                color: "var(--wb-content-secondary)",
                textDecoration: "none",
              }}
            >
              <BackIcon />
            </a>
          ) : null}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: "var(--wb-font-size-base)",
                lineHeight: "var(--wb-line-height-base)",
                fontWeight: 700,
                letterSpacing: "-0.01em",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {title}
            </div>
            {sub ? (
              <div
                className="mono"
                style={{
                  fontSize: "var(--wb-font-size-xs)",
                  lineHeight: "var(--wb-line-height-xs)",
                  color: "var(--wb-content-muted)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {sub}
              </div>
            ) : null}
          </div>
          {headerBadge ? <span style={badgeStyle}>{headerBadge}</span> : null}
        </header>

        <main
          data-anchor="shell/content"
          style={{
            width: "100%",
            minWidth: 0,
            // Pad the content clear of the fixed bars:
            // the space-16 breathing room plus each bar's
            // measured height (fallbacks are the
            // measured-typical sizes for the first frame).
            padding:
              "calc(var(--wb-space-16) + var(--wb-phone-top-h, 61px)) var(--wb-space-16) calc(var(--wb-space-16) + var(--wb-phone-tab-h, 57px))",
          }}
        >
          {route.view === "section" ? (
            <PhoneSectionNav slug={route.slug} current={route.section} />
          ) : null}
          {boundedContent}
        </main>

        <PhoneTabBar active={phoneTab} projectHref={projectHref} inboxCount={inboxCount} />
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        overscrollBehavior: "none",
        background: "var(--wb-surface-canvas)",
        color: "var(--wb-content-primary)",
        fontFamily: "var(--wb-font-ui)",
      }}
    >
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
                                <span
                                  className="mono"
                                  style={{ fontSize: "var(--wb-font-size-xs)" }}
                                >
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
          data-anchor="shell/content"
          style={{
            maxWidth: "1600px",
            margin: "0 auto",
            padding: "var(--wb-page-padding)",
            overscrollBehavior: "none",
          }}
        >
          {boundedContent}
        </main>
      </div>
    </div>
  );
}
