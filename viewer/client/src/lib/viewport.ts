// Shell sizing from the VISUAL viewport (phone scroll
// hardening). The phone shell used to size itself with
// 100dvh alone, but dvh tracks the LAYOUT viewport — and
// in the artifact's host webview the layout viewport can
// be taller than the visible area, so the shell over-sized
// and rode out of view (the owner's screenshot: the bottom
// tab bar ending at ~64% of screen height, host background
// below it). window.visualViewport tracks the visible box
// itself, so the shell consumes its height instead:
//
//   useAppViewportHeight() keeps the CSS custom property
//   --wb-app-height on the document root in sync with
//   visualViewport.height, and the phone shell root sizes
//   with var(--wb-app-height, 100dvh).
//
// The 100dvh fallback governs wherever the API is absent
// (nothing is written, the property stays unset). On
// desktop the property is written but consumed by nothing
// — the desktop root keeps minHeight: 100vh — and visual
// == layout viewport there, so desktop geometry is
// unchanged. This module is NOT a responsive seam: it
// names no width breakpoint and changes no presentation;
// lib/responsive.ts remains the only seam.

import { useEffect } from "react";

/** The custom property the phone shell root's height
 * reads. Set on the document root; inherited everywhere. */
export const APP_HEIGHT_PROPERTY = "--wb-app-height";

/** The slice of a style declaration the sync writes to —
 * structural, so the unit test drives it with a fake. */
export interface AppHeightStyleTarget {
  setProperty(name: string, value: string): void;
  removeProperty(name: string): void;
}

/** The slice of VisualViewport the sync reads. */
export interface VisualViewportShape {
  height: number;
}

/** The property value for a viewport height. Floored: the
 * shell must never exceed the visible box — an overshoot
 * of even a fraction of a pixel re-creates an outer
 * scroller, which is the defect being fixed. */
export function appHeightValue(heightPx: number): string {
  return `${Math.floor(heightPx)}px`;
}

/** Write the viewport's height into the property. Returns
 * false — and writes nothing — when there is no viewport
 * to read, leaving the CSS fallback in force. */
export function syncAppHeight(
  target: AppHeightStyleTarget,
  viewport: VisualViewportShape | null | undefined,
): boolean {
  if (viewport == null) return false;
  target.setProperty(APP_HEIGHT_PROPERTY, appHeightValue(viewport.height));
  return true;
}

/** Remove the property, restoring the CSS fallback. */
export function clearAppHeight(target: AppHeightStyleTarget): void {
  target.removeProperty(APP_HEIGHT_PROPERTY);
}

/** Keep --wb-app-height in sync with the visual viewport
 * for the app's lifetime: an initial sync, then the
 * viewport's own resize + scroll events (scroll fires when
 * the visible box moves or resizes under browser chrome).
 * A no-op where window.visualViewport is unavailable. */
export function useAppViewportHeight(): void {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (viewport == null) return;
    const style = document.documentElement.style;
    const update = () => {
      syncAppHeight(style, viewport);
    };
    update();
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);
    return () => {
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
      clearAppHeight(style);
    };
  }, []);
}
