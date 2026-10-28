// Settings — the app-level route (#/settings), the ONE
// home for settings (repo-home spec §3): Appearance
// (mode, palette, density — the ONLY appearance controls
// in the app; the shell chrome carries a Settings nav
// entry and nothing else), Workspace (the server's
// effective configuration, read-only), and Messages
// (cleanup policy in force + guarded manual controls) —
// the Workspace/Messages panels live in
// settings/SettingsPanels.tsx.
//
// The controls are the kit's (Subplan 04), consumed against
// their contracted props: ModeControl / PaletteSelect /
// DensityToggle. Applying a change is instant (selector
// switching over the shipped themes bundle, SPEC §11.2) and
// persisted client-side by the caller (lib/preferences).

import { DensityToggle } from "../components/DensityToggle";
import { ModeControl } from "../components/ModeControl";
import { PaletteSelect } from "../components/PaletteSelect";
import type { Appearance, Density, Mode } from "../lib/preferences";
import { PALETTE_OPTIONS } from "../lib/preferences";
import { ReposTrackingPanel } from "./settings/ReposTrackingPanel";
import { SettingsPanels } from "./settings/SettingsPanels";
import { sectionTitleStyle } from "./shared";

const rowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "var(--wb-space-24)",
  padding: "var(--wb-space-16) 0",
  borderBottom: "1px solid var(--wb-border-default)",
};

const labelStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
};

const hintStyle: React.CSSProperties = {
  color: "var(--wb-content-secondary)",
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  marginTop: "var(--wb-space-4)",
};

export function SettingsSection({
  appearance,
  onChange,
}: {
  appearance: Appearance;
  onChange: (next: Appearance) => void;
}) {
  return (
    <section data-anchor="settings/appearance-panel">
      <h1 style={sectionTitleStyle}>Settings</h1>
      <h2
        style={{
          fontSize: "var(--wb-font-size-xs)",
          lineHeight: "var(--wb-line-height-xs)",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--wb-content-secondary)",
        }}
      >
        Appearance
      </h2>
      <div style={rowStyle}>
        <div>
          <div style={labelStyle}>Mode</div>
          <div style={hintStyle}>System follows your operating system.</div>
        </div>
        <ModeControl
          value={appearance.mode}
          onChange={(mode: Mode) => onChange({ ...appearance, mode })}
        />
      </div>
      <div style={rowStyle}>
        <div>
          <div style={labelStyle}>Palette</div>
          <div style={hintStyle}>The token-set variant; statuses never change.</div>
        </div>
        <PaletteSelect
          value={appearance.palette}
          options={PALETTE_OPTIONS}
          onChange={(palette: string) => onChange({ ...appearance, palette })}
        />
      </div>
      <div style={rowStyle}>
        <div>
          <div style={labelStyle}>Density</div>
          <div style={hintStyle}>Compact tightens rows and padding; targets never shrink.</div>
        </div>
        <DensityToggle
          value={appearance.density}
          onChange={(density: Density) => onChange({ ...appearance, density })}
        />
      </div>
      <SettingsPanels />
      <ReposTrackingPanel />
    </section>
  );
}
