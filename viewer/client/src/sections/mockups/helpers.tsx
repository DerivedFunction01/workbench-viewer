// Shared rendering + pure filter logic for the Mockups
// section. The preview well never fabricates a mock: entries
// whose source is an artifact slug or an external reference
// have no renderable file in the harness, so the well shows
// the entry's recorded state (source, state values, ruling)
// and says what it is. Entry-dir entries get their real file
// content in the drill-in's Files panel.

import type { ReactNode } from "react";
import { Badge } from "../../components/Badge";
import { Chip, type RuledStatus } from "../../components/Chip";
import { formatShortHash } from "../../lib/format";
import { kindLabel } from "../../lib/labels";
import type { ApprovalCoverage, DerivedStaleness, FullEntry } from "./types";
import { RULED_STATUSES, type RuledStatusName } from "./types";

export function isRuledStatus(value: string): value is RuledStatusName {
  return (RULED_STATUSES as readonly string[]).includes(value);
}

export function EntryChip({ entry }: { entry: FullEntry }) {
  if (!isRuledStatus(entry.status)) return <span>{entry.status}</span>;
  return <Chip status={entry.status as RuledStatus} gate={entry.gate ?? undefined} />;
}

/** The derived badges that sit beside the ruled chip: stale
 * (with magnitude), approval coverage, needs-changes. */
export function EntryBadges({
  derived,
  approval,
  needsChanges,
}: {
  derived?: DerivedStaleness | null;
  approval?: ApprovalCoverage | null;
  needsChanges?: boolean;
}) {
  const badges: ReactNode[] = [];
  if (derived?.stale) {
    const days = Math.floor(derived.days_since_verified);
    const text = derived.drift ? "Stale · content drifted" : `Stale · ${days}d unverified`;
    badges.push(<Badge key="stale" kind="stale" text={text} />);
  }
  if (approval?.approved) {
    if (approval.covers_current) {
      badges.push(
        <Badge
          key="approved"
          kind="approved"
          text="Approved"
          stateHash={formatShortHash(approval.approved_state_sha256)}
        />,
      );
    } else {
      badges.push(<Badge key="not-covered" kind="not-covered" text="Not covered" />);
    }
  }
  if (needsChanges) {
    badges.push(<Badge key="needs-changes" kind="needs-changes" text="Needs changes" />);
  }
  if (badges.length === 0) return null;
  return <>{badges}</>;
}

export function stateValues(entry: FullEntry): Record<string, unknown> {
  return entry.state_json ?? {};
}

export function hasState(entry: FullEntry): boolean {
  return entry.state_schema != null && Object.keys(entry.state_schema).length > 0;
}

/** One featured state per state-field variation (contact
 * sheet): the recorded state, then one variation per field
 * value — variants are states, never duplicate entries. */
export function featuredStates(
  entry: FullEntry,
): { label: string; values: Record<string, unknown> }[] {
  const base = stateValues(entry);
  const out = [{ label: "As recorded", values: base }];
  if (!hasState(entry)) return out;
  const schema = entry.state_schema as Record<string, Record<string, unknown>>;
  for (const [key, spec] of Object.entries(schema)) {
    if (spec.type === "toggle") {
      const flipped = base[key] !== true;
      out.push({
        label: `${key}: ${flipped ? "on" : "off"}`,
        values: { ...base, [key]: flipped },
      });
    } else if (spec.type === "select" && Array.isArray(spec.options)) {
      for (const option of spec.options as string[]) {
        if (option !== base[key]) {
          out.push({ label: `${key}: ${option}`, values: { ...base, [key]: option } });
        }
      }
    }
    if (out.length >= 6) break;
  }
  return out.slice(0, 6);
}

/** The recorded-state summary rendered inside a preview well. */
export function PreviewSummary({
  entry,
  values,
}: {
  entry: FullEntry;
  values?: Record<string, unknown>;
}) {
  const shown = values ?? stateValues(entry);
  const keys = Object.keys(shown);
  return (
    <div style={{ fontSize: "var(--wb-font-size-sm)", lineHeight: "var(--wb-line-height-sm)" }}>
      <p style={{ margin: "0 0 var(--wb-space-8)", fontWeight: 600 }}>{entry.title}</p>
      <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
        {kindLabel(entry.kind)} · {entry.source_kind}
        {entry.source_ref ? (
          <>
            {" · "}
            {/* overflowWrap: a source_ref is an unbroken
                path token; at phone width it outruns its
                line and paints past the figure (496px in a
                356px box in the step-3 capture). */}
            <span className="mono" style={{ overflowWrap: "anywhere" }}>
              {entry.source_ref}
            </span>
          </>
        ) : null}
      </p>
      {keys.length > 0 ? (
        <ul style={{ listStyle: "none", margin: "var(--wb-space-8) 0 0", padding: 0 }}>
          {keys.map((key) => (
            <li key={key} style={{ overflowWrap: "anywhere" }}>
              <span className="mono" style={{ color: "var(--wb-content-muted)" }}>
                {key}
              </span>{" "}
              {String(shown[key])}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ margin: "var(--wb-space-8) 0 0", color: "var(--wb-content-muted)" }}>
          No internal state recorded for this entry.
        </p>
      )}
      {entry.source_kind !== "entry-dir" ? (
        <p style={{ margin: "var(--wb-space-8) 0 0", color: "var(--wb-content-muted)" }}>
          Preview unavailable — this entry is held by reference ({entry.source_kind}); its files
          live outside the harness.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pure filtering (the storyboard toolbar's logic, testable
// without a DOM)
// ---------------------------------------------------------------------------

export interface FilterState {
  statuses: ReadonlySet<string>;
  kind: string; // "" = all kinds
  staleOnly: boolean;
  triageOnly: boolean;
  search: string;
  sort: "recent" | "unverified" | "title";
}

export const DEFAULT_FILTERS: FilterState = {
  statuses: new Set<string>(),
  kind: "",
  staleOnly: false,
  triageOnly: false,
  search: "",
  sort: "recent",
};

export function filterEntries(
  entries: FullEntry[],
  filters: FilterState,
  triageIds: ReadonlySet<string>,
): FullEntry[] {
  const needle = filters.search.trim().toLowerCase();
  const out = entries.filter((entry) => {
    if (filters.statuses.size > 0 && !filters.statuses.has(entry.status)) return false;
    if (filters.kind && entry.kind !== filters.kind) return false;
    if (filters.staleOnly && !entry.derived?.stale) return false;
    if (filters.triageOnly && !triageIds.has(entry.id)) return false;
    if (needle) {
      const haystack =
        `${entry.id} ${entry.title} ${entry.kind} ${entry.status} ${entry.source_ref ?? ""}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });
  const byTitle = (a: FullEntry, b: FullEntry) => a.title.localeCompare(b.title);
  if (filters.sort === "title") out.sort(byTitle);
  if (filters.sort === "recent") {
    out.sort((a, b) => b.updated_at.localeCompare(a.updated_at) || byTitle(a, b));
  }
  if (filters.sort === "unverified") {
    out.sort(
      (a, b) =>
        (b.derived?.days_since_verified ?? 0) - (a.derived?.days_since_verified ?? 0) ||
        byTitle(a, b),
    );
  }
  return out;
}
