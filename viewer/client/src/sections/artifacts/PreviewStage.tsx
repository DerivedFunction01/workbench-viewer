import { useQuery } from "@tanstack/react-query";
import { Frame } from "../../components/Frame";
import { api } from "../../lib/api";
import type { ConfigPayload } from "../../lib/api-types";
import { configKey } from "../../lib/keys";
import type { FullEntry } from "./types";

/** The stage: the entry's main file as a real document in
 * an iframe over the companion server's byte route
 * (SPEC §7) — the page's own scripts run and its relative
 * assets resolve, which the retired JSON/srcDoc preview
 * could never do. The frame is sandboxed to scripts only:
 * an opaque origin, so the artifact page and the viewer
 * cannot reach each other. The byte route answers from the
 * server's own config, so the client reads host/port from
 * the config feed rather than assuming an address. */
export function PreviewStage({ slug, entry }: { slug: string; entry: FullEntry }) {
  const mainFile = entry.source_kind === "entry-dir" ? entry.main_file : null;
  const configQuery = useQuery({
    queryKey: configKey,
    queryFn: () => api.getConfig({}),
    enabled: mainFile != null,
  });
  const config = (configQuery.data?.payload as ConfigPayload | undefined)?.config;
  const host = typeof config?.host === "string" ? config.host : null;
  const port = typeof config?.port === "number" ? config.port : null;
  const rawUrl =
    mainFile != null && host != null && port != null
      ? `http://${host}:${port}/raw/${encodeURIComponent(slug)}/entries/${encodeURIComponent(entry.id)}/${mainFile
          .split("/")
          .map(encodeURIComponent)
          .join("/")}`
      : null;

  return (
    <Frame
      anchor="artifacts/exhibit-stage"
      title={entry.title}
      viewportLabel={`${entry.source_kind} · live page`}
      archived={entry.archived}
    >
      {mainFile == null ? (
        <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>
          Preview unavailable — this item is held by reference; its files live outside the harness.
        </p>
      ) : rawUrl == null ? (
        <p style={{ margin: 0, color: "var(--wb-content-muted)" }}>Loading preview…</p>
      ) : (
        <iframe
          title={`Rendered preview of ${entry.title}`}
          sandbox="allow-scripts"
          src={rawUrl}
          style={{
            display: "block",
            width: "100%",
            height: "560px",
            border: "1px solid var(--wb-border-default)",
            borderRadius: "var(--wb-radius-md)",
            background: "var(--wb-surface-1)",
          }}
        />
      )}
    </Frame>
  );
}
