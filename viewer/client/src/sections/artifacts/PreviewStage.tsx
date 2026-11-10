import { useMutation } from "@tanstack/react-query";
import { Button } from "../../components/Button";
import { Frame } from "../../components/Frame";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { FullEntry } from "./types";

/** The stage: the entry's open control over the hosted byte
 * route (SPEC §8.5). The page itself is NOT embedded — the
 * companion server's loopback address resolves on the
 * reader's own device, so no frame in this client can load
 * it. Instead the openEntryPage action mirrors the entry's
 * file tree into the space's hosted blob storage and this
 * control navigates to the mirror's public URL in a new
 * tab: the exact bytes, served as a real document, from an
 * address every device can reach. The mirror is a cache
 * keyed by the tree's digest; the entry dir stays the
 * source of truth. */
export function PreviewStage({ slug, entry }: { slug: string; entry: FullEntry }) {
  const mainFile = entry.source_kind === "entry-dir" ? entry.main_file : null;

  const openMutation = useMutation({
    mutationFn: () => api.openEntryPage({ slug, entryId: entry.id }),
    onSuccess: (result) => {
      if (result.status === 200 && result.payload?.url) {
        window.open(result.payload.url, "_blank", "noopener");
      }
    },
  });
  const result = openMutation.data;
  const payload = result && result.status === 200 ? result.payload : null;
  const openError = openMutation.isError
    ? "The page could not be mirrored — the action did not reach the server. Nothing was served."
    : result && result.status !== 200
      ? (result.error ?? `The mirror refused this entry (status ${result.status}).`)
      : null;

  return (
    <Frame
      anchor="artifacts/exhibit-stage"
      title={entry.title}
      viewportLabel={`${entry.source_kind} · hosted page`}
      archived={entry.archived}
    >
      {mainFile == null ? (
        <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>
          Page unavailable — this item is held by reference; its files live outside the harness.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--wb-space-8)" }}>
          <div style={{ display: "flex", gap: "var(--wb-space-8)", flexWrap: "wrap" }}>
            <Button disabled={openMutation.isPending} onClick={() => openMutation.mutate()}>
              {openMutation.isPending ? "Mirroring…" : "Open page"}
            </Button>
            {payload ? (
              <a
                href={payload.url}
                target="_blank"
                rel="noreferrer"
                className="mono"
                style={{
                  alignSelf: "center",
                  color: "var(--wb-content-secondary)",
                  overflowWrap: "anywhere",
                  fontSize: "var(--wb-font-size-sm)",
                }}
              >
                {payload.url}
              </a>
            ) : null}
          </div>
          <p style={{ margin: 0, color: "var(--wb-content-secondary)" }}>
            The page opens as its own document in a new tab — its scripts run, and its questions and
            Copy payload live in the page, per the choice kit.
          </p>
          {payload ? (
            <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>
              Hosted copy verified {formatDateTime(payload.verified_at)} · {payload.files}{" "}
              {payload.files === 1 ? "file" : "files"} mirrored
            </p>
          ) : null}
          {payload && payload.skipped.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: "var(--wb-space-16)" }}>
              {payload.skipped.map((skip) => (
                <li key={skip.path} style={{ color: "var(--wb-content-secondary)" }}>
                  Not mirrored: <span className="mono">{skip.path}</span> — {skip.reason}
                </li>
              ))}
            </ul>
          ) : null}
          {openError ? (
            <p role="alert" style={{ margin: 0, color: "var(--wb-danger)" }}>
              {openError}
            </p>
          ) : null}
        </div>
      )}
    </Frame>
  );
}
