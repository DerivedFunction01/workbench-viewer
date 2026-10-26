// Types for the Artifacts collection. The artifacts feed
// is the registry feed shape (SPEC §7) — the same entry
// rows the Mockups collection serves, kind-filtered
// server-side — so the shapes are aliased from the mockups
// types rather than redefined: the two collections can
// never drift apart in shape.

import type { MockupsFeedFull } from "../mockups/types";

export type ArtifactsFeed = MockupsFeedFull;

export type {
  EntryDetail,
  Envelope,
  FullEntry,
  PeekResult,
} from "../mockups/types";
