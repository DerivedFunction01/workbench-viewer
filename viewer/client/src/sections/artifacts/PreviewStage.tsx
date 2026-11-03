import { useQuery } from "@tanstack/react-query";
import { Frame } from "../../components/Frame";
import type { StateValues } from "../../components/StateControls";
import { api } from "../../lib/api";
import { PreviewSummary } from "../mockups/helpers";
import type { Envelope, FullEntry, PeekResult } from "./types";

/** The stage: the item's main file rendered in a sandboxed
 * iframe over the guarded peek. Content the peek refuses
 * (truncated, binary, withheld) never renders — the stage
 * falls back to the recorded-state summary with the reason
 * shown, exactly as the Files panel reports it. */
export function PreviewStage({
  slug,
  entry,
  draftState,
}: {
  slug: string;
  entry: FullEntry;
  draftState: StateValues | null;
}) {
  const mainFile = entry.source_kind === "entry-dir" ? entry.main_file : null;
  const peekQuery = useQuery({
    queryKey: ["entry-file", slug, entry.id, mainFile],
    queryFn: () => api.getEntryFile({ slug, entryId: entry.id, path: mainFile ?? "" }),
    enabled: mainFile != null,
  });
  const peekEnvelope = peekQuery.data as Envelope | undefined;
  const peek =
    peekEnvelope && peekEnvelope.status === 200 ? (peekEnvelope.payload as PeekResult) : null;

  let fallbackReason: string | null = null;
  if (mainFile == null) {
    fallbackReason =
      "Preview unavailable — this item is held by reference; its files live outside the harness.";
  } else if (peekQuery.isPending) {
    fallbackReason = null;
  } else if (!peek) {
    fallbackReason = peekEnvelope?.error ?? "The main file could not be peeked.";
  } else if (peek.withheld) {
    fallbackReason = "Preview withheld — this path is secret-shaped and is never shown here.";
  } else if (peek.is_binary) {
    fallbackReason = "Binary file — no rendered preview.";
  } else if (peek.truncated) {
    fallbackReason = "The file exceeds the peek caps, so no rendered preview is shown.";
  } else if (peek.content == null) {
    fallbackReason = "The main file returned no content to preview.";
  }

  return (
    <Frame
      anchor="artifacts/exhibit-stage"
      title={entry.title}
      viewportLabel={`${entry.source_kind} · rendered preview`}
      archived={entry.archived}
    >
      {mainFile != null && peekQuery.isPending ? (
        <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>Loading preview…</p>
      ) : peek && fallbackReason == null ? (
        <iframe
          title={`Rendered preview of ${entry.title}`}
          sandbox=""
          srcDoc={peek.content ?? ""}
          style={{
            display: "block",
            width: "100%",
            height: "560px",
            border: "1px solid var(--wb-border-default)",
            borderRadius: "var(--wb-radius-md)",
            background: "var(--wb-surface-1)",
          }}
        />
      ) : (
        <>
          <PreviewSummary entry={entry} values={draftState ?? undefined} />
          {fallbackReason ? (
            <p style={{ margin: "var(--wb-space-8) 0 0", color: "var(--wb-content-muted)" }}>
              {fallbackReason}
            </p>
          ) : null}
        </>
      )}
    </Frame>
  );
}
