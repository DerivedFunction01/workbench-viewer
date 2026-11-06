// Entry-detail data for the drill-in (split from
// MockupDetail.tsx, 2026-11-05 follow-up): the detail +
// active-feed queries, the feed-row fallback derivation,
// and the draft-state lifecycle — returning the shaped
// state the component renders from.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { StateValues } from "../../components/StateControls";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { ruledStatusLabel } from "../../lib/labels";
import { stateValues } from "./helpers";
import { toStateValues } from "./meta";
import type { EntryDetail, Envelope, FullEntry, MockupsFeedFull } from "./types";

export function useEntryDetail(slug: string, entryId: string, feedEntry: FullEntry | null) {
  const detailQuery = useQuery({
    queryKey: ["entry", slug, entryId],
    queryFn: () => api.getEntry({ slug, entryId }),
  });
  // The project's active feed — the same query the
  // section list runs, so it shares that cache entry.
  // It feeds the supersede picker (the entry's siblings,
  // chosen by title) and the "Superseded by" title lookup.
  const feedQuery = useQuery({
    queryKey: ["mockups", slug, false],
    queryFn: () => api.getMockups({ slug }),
  });
  const feedEnvelope = feedQuery.data as Envelope | undefined;
  const feed: MockupsFeedFull | null =
    feedEnvelope && feedEnvelope.status === 200 && feedEnvelope.payload
      ? (feedEnvelope.payload as MockupsFeedFull)
      : null;
  const detailEnvelope = detailQuery.data as Envelope | undefined;
  const detail =
    detailEnvelope && detailEnvelope.status === 200
      ? (detailEnvelope.payload as EntryDetail)
      : null;
  const detailError =
    detailEnvelope && detailEnvelope.status !== 200
      ? (detailEnvelope.error ?? "the entry detail could not be loaded.")
      : null;

  // The feed row is a complete fallback for everything except
  // history/files: if the detail action refuses, the drill-in
  // still renders the entry's recorded truth from the feed.
  const entry: FullEntry | null = detail?.entry ?? feedEntry;
  const derived = detail?.derived ?? feedEntry?.derived ?? null;
  const approval = detail?.approval ?? feedEntry?.approval ?? null;

  const [draftState, setDraftState] = useState<StateValues | null>(() =>
    entry ? toStateValues(entry) : null,
  );

  useEffect(() => {
    if (entry) {
      setDraftState(toStateValues(entry));
    }
  }, [entry]);

  const savedStateJson = useMemo(
    () => JSON.stringify(stateValues(entry ?? ({} as FullEntry))),
    [entry],
  );
  const draftDirty =
    draftState != null && entry != null && JSON.stringify(draftState) !== savedStateJson;

  const latestReview = detail?.latest_review ?? null;
  const needsChanges = latestReview?.payload?.disposition === "needs-changes";

  // Supersede candidates: the project's other entries
  // from the active feed (archived entries are not in
  // it). Options are labelled by title + ruled status —
  // never by id; a shared title earns a created-date
  // suffix so the choices stay distinguishable.
  const supersedeCandidates = (feed?.entries ?? []).filter(
    (candidate) => candidate.id !== entry?.id,
  );
  const candidateTitleCounts = new Map<string, number>();
  for (const candidate of supersedeCandidates) {
    candidateTitleCounts.set(candidate.title, (candidateTitleCounts.get(candidate.title) ?? 0) + 1);
  }
  const candidateLabel = (candidate: FullEntry): string => {
    const base = `${candidate.title} · ${ruledStatusLabel(candidate.status)}`;
    return (candidateTitleCounts.get(candidate.title) ?? 0) > 1
      ? `${base} · ${formatDate(candidate.created_at)}`
      : base;
  };
  // "Superseded by" reads as a title when the target is
  // in the active feed; the raw id is the fallback for a
  // target the feed no longer carries (e.g. archived).
  const supersededByTitle = entry?.superseded_by
    ? ((feed?.entries ?? []).find((candidate) => candidate.id === entry.superseded_by)?.title ??
      null)
    : null;

  return {
    detailQuery,
    detail,
    detailError,
    entry,
    derived,
    approval,
    draftState,
    setDraftState,
    draftDirty,
    latestReview,
    needsChanges,
    supersedeCandidates,
    candidateLabel,
    supersededByTitle,
  };
}
