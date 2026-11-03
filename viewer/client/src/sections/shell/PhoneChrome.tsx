import { sectionLabel } from "../../lib/labels";
import {
  homeHref,
  inboxHref,
  reposHref,
  type SectionId,
  sectionHref,
  settingsHref,
} from "../../lib/routing";
import { badgeStyle } from "../shared";

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

export function BackIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

function ReposIcon() {
  return (
    <svg {...tabIconProps} aria-hidden="true">
      <circle cx="6" cy="5" r="2.2" />
      <circle cx="6" cy="19" r="2.2" />
      <circle cx="18" cy="7" r="2.2" />
      <path d="M6 7.2v9.6" />
      <path d="M18 9.2c0 4.8-5.4 3.9-9 6" />
    </svg>
  );
}

export type PhoneTab = "home" | "project" | "repos" | "inbox" | "settings";

export function PhoneTabBar({
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
    { id: "repos", label: "Repos", href: reposHref(), icon: <ReposIcon /> },
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
        gridTemplateColumns: "repeat(5, 1fr)",
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

export function PhoneSectionNav({ slug, current }: { slug: string; current: SectionId }) {
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
