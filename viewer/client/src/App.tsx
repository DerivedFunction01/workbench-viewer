// The shell — composition only (contracts audit B1,
// 2026-11-05): the status model and its queries live
// in sections/shell/ShellStatus, the rail in ShellRail,
// the route table in ShellRoutes, the phone chrome in
// PhoneChrome. What remains here is the frame: hash
// routing, the appearance state, the phone bars'
// measured-height plumbing, and the two presentations'
// outer wrappers.
//
// Routing is hash-based (lib/routing): #/ is the workspace
// home (repo-home §4), #/p/<slug>/<section>[/<item>] the
// per-project sections (Overview first, repo-home §2),
// #/board the cross-project board, #/inbox the message
// inbox, #/settings Settings. Appearance controls live
// on the Settings route ONLY (repo-home spec §3, the
// owner's ruling): no toggles, no gear menus in this
// chrome. Every section's queries are scoped by the
// selected project; switching project re-scopes them all.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { SectionBoundary } from "./components/SectionBoundary";
import { sectionLabel } from "./lib/labels";
import type { Appearance } from "./lib/preferences";
import { applyAppearance, loadAppearance, saveAppearance } from "./lib/preferences";
import { useIsPhone } from "./lib/responsive";
import { parseRoute, pickerHref, type Route, sectionHref } from "./lib/routing";
import { resetContentScroll } from "./lib/scroll";
import { PhoneSectionNav, type PhoneTab, PhoneTabBar } from "./sections/shell/PhoneChrome";
import { ShellRail } from "./sections/shell/ShellRail";
import { ShellRoutes } from "./sections/shell/ShellRoutes";
import { DesktopHeader, PhoneTopBar, useShellStatus } from "./sections/shell/ShellStatus";

function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
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

  const status = useShellStatus(route);
  const { selected } = status;

  const breadcrumb = (() => {
    if (route.view === "settings") return "Settings";
    if (route.view === "inbox") return "Inbox";
    if (route.view === "picker") return "Projects";
    if (route.view === "repos") return route.repoId ? `Repos / ${route.repoId}` : "Repos";
    if (route.view === "board-all") return "Board · all projects";
    if (route.view === "section") {
      const name = selected?.name ?? route.slug;
      const section = sectionLabel(route.section);
      return route.item ? `${name} / ${section} / ${route.item}` : `${name} / ${section}`;
    }
    return "Workspace";
  })();

  // The routed content behind the error boundary
  // (components/SectionBoundary): a section exception
  // degrades to the boundary's fallback panel, never a
  // blank viewer. Keyed by the route — navigating away
  // remounts the boundary and clears a stuck fallback.
  const boundedContent = (
    <SectionBoundary key={JSON.stringify(route)}>
      <ShellRoutes
        route={route}
        selected={selected}
        projectsPending={status.projectsQuery.isPending}
        appearance={appearance}
        onAppearanceChange={changeAppearance}
      />
    </SectionBoundary>
  );

  if (isPhone) {
    // Phone shell (mobile variant): top bar + optional
    // section nav + content + bottom tab bar, one column.
    const phoneTab: PhoneTab =
      route.view === "inbox"
        ? "inbox"
        : route.view === "settings"
          ? "settings"
          : route.view === "repos"
            ? "repos"
            : route.view === "home" || route.view === "picker"
              ? "home"
              : "project";
    // The Project tab never auto-selects: with a project
    // in scope it opens that project; with none it opens
    // the chooser. Picking a project out of an ordering
    // is how the tab used to land on a fixture project.
    const projectHref =
      status.routeSlugValue != null ? sectionHref(status.routeSlugValue, "overview") : pickerHref();
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
        <PhoneTopBar route={route} status={status} />

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

        <PhoneTabBar active={phoneTab} projectHref={projectHref} inboxCount={status.inboxCount} />
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
      <ShellRail route={route} status={status} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <DesktopHeader breadcrumb={breadcrumb} />

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
