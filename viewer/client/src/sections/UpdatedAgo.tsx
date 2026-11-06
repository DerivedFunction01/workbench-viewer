// UpdatedAgo — the visible-freshness label
// (cache-refresh plan, design point 6): how long ago
// a feed payload was captured, from its served
// `captured_at` stamp. Computed at render time — the
// sections' 30 s poll re-renders it, so there is no
// local timer. An absent or unparseable stamp renders
// nothing: honest absence over a guessed age.

import { metaStyle } from "./shared";

export function UpdatedAgo({ capturedAt }: { capturedAt?: string | null }) {
  if (!capturedAt) return null;
  const then = new Date(capturedAt).getTime();
  if (Number.isNaN(then)) return null;
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  const text =
    seconds < 60
      ? `Updated ${seconds}s ago`
      : seconds < 3600
        ? `Updated ${Math.floor(seconds / 60)}m ago`
        : `Updated ${Math.floor(seconds / 3600)}h ago`;
  return <span style={metaStyle}>{text}</span>;
}
