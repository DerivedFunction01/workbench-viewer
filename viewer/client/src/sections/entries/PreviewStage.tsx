import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Frame } from "../../components/Frame";
import { api } from "../../lib/api";
import { useIsPhone } from "../../lib/responsive";
import type { FullEntry } from "./types";

interface PagePayload {
  contentType: string | null;
  bodyBase64: string;
  bytes: number;
}

/** Decode base64 to text the way the bytes arrived: the
 * byte route serves the file verbatim, so the decode is
 * byte-exact (atob to bytes, bytes as UTF-8) and the
 * stage renders the text unmodified. */
function decodePage(bodyBase64: string): string {
  const binary = atob(bodyBase64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

/** The stage: the entry's page itself, rendered in place
 * (SPEC §8.5). No client can load the page from the
 * companion server — its loopback address resolves on
 * the reader's own device — so the bytes ride the bridge
 * instead: the getEntryPage action fetches the main
 * file's exact bytes over the raw contract, and this
 * frame renders them as a document with its scripts
 * running, sandboxed to an opaque origin (the page
 * cannot reach the viewer, the viewer cannot reach into
 * the page). Freshness is per open: the query keys on
 * the entry's recorded fingerprint, so a rebuilt page
 * renders its new bytes on the next open. A refusal —
 * secret-shaped, over the byte bound, bridge down —
 * shows its reason in the stage, never a partial page. */
export function PreviewStage({ slug, entry }: { slug: string; entry: FullEntry }) {
  const isPhone = useIsPhone();
  const mainFile = entry.source_kind === "entry-dir" ? entry.main_file : null;

  const pageQuery = useQuery({
    queryKey: ["entry-page", slug, entry.id, entry.content_sha256],
    queryFn: () => api.getEntryPage({ slug, entryId: entry.id }),
    enabled: mainFile != null,
  });
  const envelope = pageQuery.data;
  const payload =
    envelope && envelope.status === 200 ? (envelope.payload as PagePayload | null) : null;
  const pageText = useMemo(() => (payload ? decodePage(payload.bodyBase64) : null), [payload]);
  const pageError = pageQuery.isError
    ? "The page could not be fetched — the action did not reach the server. Nothing was rendered."
    : envelope && envelope.status !== 200
      ? (envelope.error ?? `The byte route refused this page (status ${envelope.status}).`)
      : null;

  return (
    <Frame
      anchor="artifacts/exhibit-stage"
      title={entry.title}
      viewportLabel={`${entry.source_kind} · rendered page`}
      archived={entry.archived}
    >
      {mainFile == null ? (
        <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>
          Page unavailable — this item is held by reference; its files live outside the harness.
        </p>
      ) : pageQuery.isPending ? (
        <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>Loading page…</p>
      ) : pageError ? (
        <p role="alert" style={{ margin: 0, color: "var(--wb-danger)" }}>
          {pageError}
        </p>
      ) : pageText != null ? (
        <iframe
          title={`Rendered page of ${entry.title}`}
          sandbox="allow-scripts"
          srcDoc={pageText}
          style={{
            display: "block",
            width: "100%",
            height: isPhone ? "calc(100dvh - 220px)" : "560px",
            minHeight: isPhone ? "320px" : undefined,
            border: "1px solid var(--wb-border-default)",
            borderRadius: "var(--wb-radius-md)",
            background: "var(--wb-surface-1)",
          }}
        />
      ) : null}
    </Frame>
  );
}
