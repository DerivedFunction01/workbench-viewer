// The ONE responsive seam (mobile variant build): every
// phone presentation in the client hangs off this module —
// the breakpoint value, its media query, and the hook the
// shell and sections read. No other file names a width
// breakpoint; a future width variant extends THIS module,
// never a second literal elsewhere.
//
// The value: the approved mobile mockup
// (workbench-viewer-mobile-variant-mockup) renders its
// phone exhibits at a 390px design width, and the mockup
// stylesheet's own small-screen threshold is 480px
// (@media (max-width: 480px) for its compact treatment).
// The phone presentation therefore applies at <= 480px —
// the 390px design width sits inside it with margin —
// and every width above it renders exactly the desktop
// presentation, unchanged. One breakpoint by ruling: no
// tablet-specific variant in v1.

import { useEffect, useState } from "react";

export const PHONE_MAX_WIDTH_PX = 480;

export const PHONE_MEDIA_QUERY = `(max-width: ${PHONE_MAX_WIDTH_PX}px)`;

/** True while the viewport is at phone width. Reactive:
 * crossing the breakpoint re-renders the caller with the
 * other presentation — routing and section state are
 * untouched, presentation only. */
export function useIsPhone(): boolean {
  const [isPhone, setIsPhone] = useState<boolean>(
    () => typeof window !== "undefined" && window.matchMedia(PHONE_MEDIA_QUERY).matches,
  );
  useEffect(() => {
    const mql = window.matchMedia(PHONE_MEDIA_QUERY);
    const onChange = () => setIsPhone(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  return isPhone;
}
