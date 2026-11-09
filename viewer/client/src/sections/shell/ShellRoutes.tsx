// The route table (contracts audit B1, 2026-11-05):
// which section a route renders. The content is
// identical for both presentations — only the chrome
// around it differs — so the switch lives here once
// and App.tsx composes it behind the error boundary.

import type { ProjectSummary } from "../../lib/api-types";
import type { Appearance } from "../../lib/preferences";
import { homeHref, type Route } from "../../lib/routing";
import { ArtifactsSection } from "../artifacts/Artifacts";
import { BoardSection } from "../board/Board";
import { HomeSection, ProjectPickerSection } from "../homepage/Home";
import { InboxSection } from "../inbox/Inbox";
import { MockupsSection } from "../mockups/Mockups";
import { OverviewSection } from "../overview/Overview";
import { PlansSection } from "../plans/Plans";
import { ReposSection } from "../repos/Repos";
import { SettingsSection } from "../settings/Settings";
import { TodosSection } from "../todos/Todos";

export function ShellRoutes({
  route,
  selected,
  projectsPending,
  appearance,
  onAppearanceChange,
}: {
  route: Route;
  selected: ProjectSummary | null;
  projectsPending: boolean;
  appearance: Appearance;
  onAppearanceChange: (next: Appearance) => void;
}) {
  if (route.view === "settings") {
    return <SettingsSection appearance={appearance} onChange={onAppearanceChange} />;
  }
  if (route.view === "inbox") {
    return <InboxSection />;
  }
  if (route.view === "picker") {
    return <ProjectPickerSection />;
  }
  if (route.view === "board-all") {
    return <BoardSection slug={null} projectName={null} />;
  }
  if (route.view === "repos") {
    return <ReposSection repoId={route.repoId} />;
  }
  if (route.view === "section") {
    if (selected == null && !projectsPending) {
      return (
        <p style={{ color: "var(--wb-content-secondary)" }}>
          Project <span className="mono">{route.slug}</span> is not in the current sweep.{" "}
          <a href={homeHref()} style={{ color: "var(--wb-accent)" }}>
            Back to projects
          </a>
        </p>
      );
    }
    if (route.section === "overview") {
      return <OverviewSection slug={route.slug} projectName={selected?.name ?? route.slug} />;
    }
    if (route.section === "mockups") {
      return <MockupsSection slug={route.slug} projectName={selected?.name ?? route.slug} />;
    }
    if (route.section === "artifacts") {
      return (
        <ArtifactsSection
          slug={route.slug}
          projectName={selected?.name ?? route.slug}
          item={route.item}
        />
      );
    }
    if (route.section === "plans") {
      return (
        <PlansSection
          slug={route.slug}
          projectName={selected?.name ?? route.slug}
          item={route.item}
        />
      );
    }
    if (route.section === "todos") {
      return <TodosSection slug={route.slug} projectName={selected?.name ?? route.slug} />;
    }
    return <BoardSection slug={route.slug} projectName={selected?.name ?? route.slug} />;
  }
  return <HomeSection />;
}
