// Appearance preferences — mode, palette, density — persisted
// client-side and applied to the document root as
// data-mode / data-palette / data-density, which is exactly
// what the generated themes CSS selects on (themes/*.css:
// `[data-palette="olive"][data-mode="dark"]`,
// `[data-density="compact"]`; mode "system" = no data-mode
// attribute, so the themes' prefers-color-scheme rules rule).
//
// Persistence: localStorage. The space SDK exposes no client
// state store (its client surface is the action client + the
// shared QueryClient), and these are per-browser UI
// preferences — the artifact's socket state is for data the
// server owns. One key, one JSON object, validated on read.

export type Mode = "system" | "light" | "dark";
export type Density = "comfortable" | "compact";

export interface Appearance {
  mode: Mode;
  palette: string;
  density: Density;
}

export const PALETTE_OPTIONS: { id: string; label: string }[] = [
  { id: "olive", label: "Olive" },
  { id: "teal", label: "Teal" },
];

export const DEFAULT_APPEARANCE: Appearance = {
  mode: "system",
  palette: "olive",
  density: "comfortable",
};

const STORAGE_KEY = "wb-viewer.appearance";

const MODES: Mode[] = ["system", "light", "dark"];
const DENSITIES: Density[] = ["comfortable", "compact"];

export function loadAppearance(): Appearance {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_APPEARANCE;
    const parsed = JSON.parse(raw) as Partial<Appearance>;
    return {
      mode: MODES.includes(parsed.mode as Mode) ? (parsed.mode as Mode) : DEFAULT_APPEARANCE.mode,
      palette:
        typeof parsed.palette === "string" &&
        PALETTE_OPTIONS.some((option) => option.id === parsed.palette)
          ? parsed.palette
          : DEFAULT_APPEARANCE.palette,
      density: DENSITIES.includes(parsed.density as Density)
        ? (parsed.density as Density)
        : DEFAULT_APPEARANCE.density,
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

export function saveAppearance(appearance: Appearance): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(appearance));
  } catch {
    // Storage unavailable (private mode, quota): the setting
    // still applies for this session via applyAppearance.
  }
}

/** Apply instantly: selector switching over the one shipped
 * bundle — never a stylesheet swap or fetch (SPEC §11.2). */
export function applyAppearance(appearance: Appearance): void {
  const root = document.documentElement;
  if (appearance.mode === "system") {
    root.removeAttribute("data-mode");
  } else {
    root.setAttribute("data-mode", appearance.mode);
  }
  root.setAttribute("data-palette", appearance.palette);
  root.setAttribute("data-density", appearance.density);
}
