// KitSpecimen — the kit specimen harness (NOT a section
// component; sections never import it). Renders every kit
// component in its contracted variants with local fixture
// state, so the contracts matrix is reviewable in one render.
// Justified past the ~300-line guideline in
// docs/component-contracts.md#specimen on exactly that ground.
import { type ReactNode, useState } from "react";
import { AnnotationBadge, annotationMarkStyle, selectionMarkStyle } from "./AnnotationBadge";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { Chip, type RuledStatus } from "./Chip";
import { DataTable } from "./DataTable";
import { DegradedBanner } from "./DegradedBanner";
import { DensityToggle, type DensityValue } from "./DensityToggle";
import { EmptyState } from "./EmptyState";
import { Frame } from "./Frame";
import { Lane } from "./Lane";
import { ModeControl, type ModeValue } from "./ModeControl";
import { PaletteSelect } from "./PaletteSelect";
import { SegmentedControl } from "./SegmentedControl";
import { Sheet } from "./Sheet";
import { StateControls, type StateValues } from "./StateControls";
import { Toggle } from "./Toggle";
import { Tooltip } from "./Tooltip";
import { TriageRow } from "./TriageRow";

const STATUSES: RuledStatus[] = [
  "canonical",
  "implemented",
  "deferred",
  "unexplored",
  "hard-gate",
  "abandoned",
];

const VALID_SCHEMA = {
  stacking: { type: "toggle", label: "Stacking" },
  density_mode: { type: "select", options: ["comfortable", "compact"] },
  data_mode: {
    type: "select",
    options: ["empty", "sample", "full", "overflow", "error", "stale"],
  },
  columns: { type: "number", min: 1, max: 6, step: 1 },
  caption: { type: "text" },
};

const INVALID_SCHEMA = {
  mystery: { type: "dial" },
  broken_select: { type: "select" },
  bad_toggle: { type: "toggle" },
};

type FixtureRow = { id: string; name: string; steps: number };
const ROWS: FixtureRow[] = [
  { id: "a", name: "Foundations", steps: 4 },
  { id: "b", name: "Component kit", steps: 3 },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-6">
      <h2
        className="mb-3 text-xs font-semibold tracking-[0.06em] uppercase"
        style={{ color: "var(--wb-content-secondary)" }}
      >
        {title}
      </h2>
      <div className="flex flex-wrap items-start gap-3">{children}</div>
    </section>
  );
}

export function KitSpecimen() {
  const [pressed, setPressed] = useState(false);
  const [on, setOn] = useState(true);
  const [mode, setMode] = useState<ModeValue>("system");
  const [density, setDensity] = useState<DensityValue>("comfortable");
  const [palette, setPalette] = useState("olive");
  const [bigPalette, setBigPalette] = useState("olive");
  const [seg, setSeg] = useState("list");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selected, setSelected] = useState("a");
  const [state, setState] = useState<StateValues>({
    stacking: true,
    density_mode: "comfortable",
    data_mode: "sample",
    columns: 3,
    caption: "Hello",
  });

  return (
    <div style={{ backgroundColor: "var(--wb-surface-canvas)", padding: "var(--wb-space-24)" }}>
      <Section title="Chip — ruled statuses">
        {STATUSES.map((s) => (
          <Chip key={s} status={s} gate={s === "hard-gate" ? "the owner ruling" : undefined} />
        ))}
        <Chip status="canonical" pressed={pressed} onPress={() => setPressed(!pressed)} />
      </Section>

      <Section title="Badge — derived / review">
        <Badge kind="stale" text="Stale · 23d unverified" />
        <Badge kind="stale" text="Stale · drift" />
        <Badge kind="not-covered" text="Approval doesn't cover current state" />
        <Badge kind="needs-changes" text="Needs changes · 2 open" />
        <Badge kind="approved" text="Approved" stateHash="a3f9c1" />
        <Badge kind="in-triage" text="In triage" />
      </Section>

      <Section title="AnnotationBadge — message lifecycle + marks">
        <AnnotationBadge state="sent" />
        <AnnotationBadge state="acknowledged" />
        <AnnotationBadge state="done" />
        <AnnotationBadge state="draft" />
        <AnnotationBadge state="archived" />
        <p className="text-sm" style={{ margin: 0 }}>
          A <mark style={selectionMarkStyle}>live selection</mark> wears the palette accent; a{" "}
          <mark style={annotationMarkStyle}>saved annotation</mark> wears Okabe orange.
        </p>
      </Section>

      <Section title="Button">
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="danger">Delete entry</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="primary" disabled>
          Disabled
        </Button>
        <Tooltip text="Row action">
          <Button variant="ghost" iconOnly ariaLabel="More actions">
            ⋯
          </Button>
        </Tooltip>
      </Section>

      <Section title="Toggle / Segmented / settings controls">
        <Toggle checked={on} onChange={setOn} label="Stacking" />
        <SegmentedControl
          options={[
            { value: "list", label: "List" },
            { value: "grid", label: "Grid" },
          ]}
          value={seg}
          onChange={setSeg}
          ariaLabel="View"
        />
        <ModeControl value={mode} onChange={setMode} />
        <DensityToggle value={density} onChange={setDensity} />
        <PaletteSelect
          value={palette}
          onChange={setPalette}
          options={[
            { id: "olive", label: "Olive" },
            { id: "teal", label: "Teal" },
          ]}
        />
        <PaletteSelect
          value={bigPalette}
          onChange={setBigPalette}
          options={["olive", "teal", "sand", "slate", "plum"].map((id) => ({
            id,
            label: id.charAt(0).toUpperCase() + id.slice(1),
          }))}
        />
      </Section>

      <Section title="Card / Frame / Lane">
        <Card title="A card" anchor="specimen/card" actions={<Button variant="ghost">Act</Button>}>
          <p className="text-sm">Card body text.</p>
        </Card>
        <Frame
          title="Sample mock"
          viewportLabel="1440 × 900 · dark"
          footer={
            <>
              <Chip status="canonical" />
              <Badge kind="stale" text="Stale · 3d unverified" />
            </>
          }
        >
          <p className="text-sm">Mock content in the sunken well.</p>
        </Frame>
        <Frame title="Archived mock" archived footer={<Chip status="abandoned" />}>
          <p className="text-sm">Archived content.</p>
        </Frame>
        <Lane title="Review queue" count={2} accent>
          <p className="text-sm">Card placeholder</p>
        </Lane>
        <Lane title="Doing" count={9} countWarning>
          <p className="text-sm">Card placeholder</p>
        </Lane>
      </Section>

      <Section title="Sheet / EmptyState / DegradedBanner / TriageRow">
        <Button variant="secondary" onClick={() => setSheetOpen(true)}>
          Open sheet
        </Button>
        <Sheet
          open={sheetOpen}
          title="Approve this state?"
          onClose={() => setSheetOpen(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setSheetOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={() => setSheetOpen(false)}>
                Approve
              </Button>
            </>
          }
        >
          <p className="text-sm">The state snapshot rides in the approval record.</p>
        </Sheet>
        <EmptyState message="No mockups match these filters" detail="Try clearing a filter." />
        <DegradedBanner
          message="Mockups is degraded: the registry database is locked."
          detail="Retry after the writer finishes."
        />
        <DegradedBanner
          tone="source-format"
          message="This plan is in source format."
          detail="It renders whole as formatted markdown."
        />
        <TriageRow
          title="Points detail mockup"
          meta="example-project-legacy · 3d old"
          leading={<Chip status="unexplored" />}
          badges={<Badge kind="stale" text="Stale · drift" />}
          onOpen={() => undefined}
        />
      </Section>

      <Section title="DataTable">
        <DataTable
          ariaLabel="Fixture plans"
          columns={[
            { key: "name", header: "Plan" },
            { key: "steps", header: "Steps", numeric: true },
          ]}
          rows={ROWS}
          rowKey={(r) => r.id}
          selectedKey={selected}
          onRowSelect={setSelected}
          empty={<EmptyState message="No plans" />}
        />
      </Section>

      <Section title="StateControls — valid schema">
        <StateControls
          schema={VALID_SCHEMA}
          values={state}
          onChange={(k, v) => setState((prev) => ({ ...prev, [k]: v }))}
        />
      </Section>

      <Section title="StateControls — invalid schema">
        <StateControls
          schema={INVALID_SCHEMA}
          values={{ bad_toggle: "yes" as unknown as boolean }}
          onChange={() => undefined}
        />
      </Section>
    </div>
  );
}
