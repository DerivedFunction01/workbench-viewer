// The shell's status cluster (contracts audit B1,
// 2026-11-05): the queries the chrome lives on —
// projects, health, home, config, the inbox badge, the
// board portions behind the doing badge, and the
// per-project triage counts — with their derivations,
// plus the two header renderings that consume them
// (the phone top bar and the desktop header). The rail
// is ShellRail; the routed content is ShellRoutes;
// App.tsx is composition only.

import { useQueries, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../../lib/api";
import type {
  BoardProjectPayload,
  HomePayload,
  MockupsFeed,
  ProjectSummary,
} from "../../lib/api-types";
import { groupProjects } from "../../lib/grouping";
import {
  artifactsKey,
  boardKey,
  configKey,
  healthKey,
  homeKey,
  messagesKey,
  mockupsKey,
  projectsKey,
} from "../../lib/keys";
import { homeHref, type Route, reposHref, sectionHref } from "../../lib/routing";
import { RefreshButton } from "../RefreshButton";
import { badgeStyle } from "../shared";
import { BackIcon } from "./PhoneChrome";

export function projectStatus(project: ProjectSummary): { word: string; degraded: boolean } {
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

export function useShellStatus(route: Route) {
  const projectsQuery = useQuery({
    queryKey: projectsKey,
    queryFn: () => api.listProjects({}),
    refetchInterval: 30000,
  });
  const healthQuery = useQuery({
    queryKey: healthKey,
    queryFn: () => api.getHealth({}),
    refetchInterval: 30000,
  });
  const homeQuery = useQuery({
    queryKey: homeKey,
    queryFn: () => api.getHome({}),
    refetchInterval: 30000,
  });
  const homeRows = useMemo(
    () => (homeQuery.data?.payload as unknown as HomePayload | null)?.projects ?? null,
    [homeQuery.data],
  );
  const configQuery = useQuery({
    queryKey: configKey,
    queryFn: () => api.getConfig({}),
  });
  const inboxQuery = useQuery({
    queryKey: messagesKey("", "sent"),
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
  // The doing badge assembles the same per-project board
  // portions the Board section renders — same query keys,
  // so the cache is shared and nothing fetches twice.
  const portionQueries = useQueries({
    queries: projects.map((p) => ({
      queryKey: boardKey(p.slug),
      queryFn: () => api.getBoardProject({ slug: p.slug }),
    })),
  });
  const portions: BoardProjectPayload[] = [];
  let portionsPending = projects.length === 0;
  portionQueries.forEach((q) => {
    const payload = q.data?.payload as BoardProjectPayload | undefined;
    if (q.isPending || !payload) {
      portionsPending = true;
      return;
    }
    portions.push(payload);
  });

  const routeSlugValue = route.view === "section" ? route.slug : null;
  const selected = routeSlugValue
    ? (projects.find((project) => project.slug === routeSlugValue) ?? null)
    : null;

  const triageQuery = useQuery({
    queryKey: mockupsKey(selected?.slug),
    queryFn: () => api.getMockups({ slug: selected?.slug ?? "" }),
    // biome-ignore lint/complexity/useOptionalChain: the boolean form is load-bearing — `selected?.sections.mockups` evaluates to undefined with no project selected, and React Query treats enabled: undefined as enabled (the query would fire with an empty slug and 422)
    enabled: selected != null && selected.sections.mockups,
  });
  const triageCount =
    (triageQuery.data?.payload as unknown as MockupsFeed | null)?.triage.length ?? null;
  const artifactsTriageQuery = useQuery({
    queryKey: artifactsKey(selected?.slug),
    queryFn: () => api.getArtifacts({ slug: selected?.slug ?? "" }),
    // biome-ignore lint/complexity/useOptionalChain: same as the mockups query above — undefined would read as enabled to React Query
    enabled: selected != null && selected.sections.artifacts,
  });
  const artifactsTriageCount =
    (artifactsTriageQuery.data?.payload as unknown as MockupsFeed | null)?.triage.length ?? null;
  const doingCount = portionsPending
    ? null
    : portions.reduce(
        (sum, portion) =>
          sum +
          (portion.counts.todos.doing ?? 0) +
          (portion.counts.plans.doing ?? 0) +
          portion.counts.review_queue,
        0,
      );

  return {
    projectsQuery,
    projects,
    health,
    serverOk,
    editingOn,
    homeRows,
    projectGroups,
    inboxCount,
    portions,
    portionsPending,
    doingCount,
    triageCount,
    artifactsTriageCount,
    routeSlugValue,
    selected,
  };
}

export type ShellStatus = ReturnType<typeof useShellStatus>;

// The phone top bar: back affordance, title/sub-line,
// the header badge, and the refresh control. Title and
// badge derive from the route and the status model.
export function PhoneTopBar({ route, status }: { route: Route; status: ShellStatus }) {
  const { selected, homeRows, portions, portionsPending } = status;
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
  } else if (route.view === "repos") {
    title = "Repos";
    sub = route.repoId;
    backHref = route.repoId ? reposHref() : homeHref();
    backLabel = route.repoId ? "Back to repos" : "Back to Home";
  } else if (route.view === "board-all") {
    title = "Board";
    sub = "all projects";
    backHref = homeHref();
    if (!portionsPending) {
      const total = portions.reduce(
        (n, portion) =>
          n +
          portion.counts.review_queue +
          Object.values(portion.counts.todos).reduce((m, c) => m + c, 0) +
          Object.values(portion.counts.plans).reduce((m, c) => m + c, 0),
        0,
      );
      headerBadge = `${total} cards`;
    }
  } else if (route.view === "section") {
    backHref = route.item ? sectionHref(route.slug, route.section) : homeHref();
    backLabel = route.item ? "Back to list" : "Back to Home";
    if (route.section === "board") {
      title = "Board";
      sub = route.slug;
      const scoped = portions.find((portion) => portion.slug === route.slug);
      if (scoped) {
        const total =
          scoped.counts.review_queue +
          Object.values(scoped.counts.todos).reduce((m, c) => m + c, 0) +
          Object.values(scoped.counts.plans).reduce((m, c) => m + c, 0);
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
      <RefreshButton />
    </header>
  );
}

// The desktop header: brand, breadcrumb, refresh.
export function DesktopHeader({ breadcrumb }: { breadcrumb: string }) {
  return (
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
      <RefreshButton style={{ marginLeft: "auto" }} />
    </header>
  );
}
