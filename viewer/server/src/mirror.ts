// The hosted byte route's action (2026-11-10): the one
// action that is not a thin proxy. The companion server's
// loopback address resolves on the reader's own device,
// so no client can load an entry page from it; instead
// this action fetches the entry's file tree over the
// bridge (detail over wbApi, exact bytes over wbRaw) and
// mirrors it verbatim into the space's hosted blob
// storage, returning the mirror's public URL. The mirror
// is a cache keyed by the tree's digest — the entry dir
// on disk stays the source of truth. Split from
// actions.ts by intent (the actions file carries the
// proxy set; this module carries the mirror).
//
// Byte handling is WebCrypto / Uint8Array throughout:
// action code runs on the platform runtime, which rejects
// Node host modules (node:crypto, Buffer) — the first
// publish proved that and adapted this file space-side;
// the adaptation is canonical here now, digest-proven
// identical to the Node form (the tree digest over the
// dogfood entry matches both ways).

import { defineAction, z } from "@hatch/space-sdk";
import { privileged } from "@space/privileged";
import { callServer, callServerRaw } from "./bridge";

const enc = encodeURIComponent;

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function sha256Hex(data: Uint8Array | string): Promise<string> {
  const input = typeof data === "string" ? new TextEncoder().encode(data) : data;
  const digest = await crypto.subtle.digest("SHA-256", input);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// The mirror's result: the public URL, when this open last
// verified the mirror, how many files it holds, the tree
// digest the mirror is keyed by, and the files the byte
// route refused (named, never silently dropped). The
// envelope is the bridge's own {status, payload, error}.
const mirrorPayload = z.looseObject({
  url: z.string(),
  verified_at: z.string(),
  files: z.number(),
  digest: z.string(),
  skipped: z.array(z.looseObject({ path: z.string(), reason: z.string() })),
});
const mirrorResult = z.object({
  status: z.number(),
  payload: mirrorPayload.nullable(),
  error: z.string().nullable(),
});

export type MirrorResult = z.infer<typeof mirrorResult>;

export const openEntryPage = defineAction({
  description:
    "Mirror an entry's page tree into hosted blob storage and return its public URL (the hosted byte route).",
  request: z.object({ slug: z.string().min(1), entryId: z.string().min(1) }),
  response: mirrorResult,
  privileged: [privileged.wbApi, privileged.wbRaw],
  async handler(ctx, args) {
    const fail = (status: number, error: string) => ({ status, payload: null, error });
    const detail = await callServer<{
      entry: { main_file: string | null; source_kind: string };
      files: { path: string; is_main: boolean }[];
    }>(ctx, `/api/projects/${enc(args.slug)}/entries/${enc(args.entryId)}`);
    if (detail.error != null || detail.payload == null) {
      return fail(detail.status, detail.error ?? "entry detail unavailable");
    }
    const { entry, files } = detail.payload;
    if (entry.source_kind !== "entry-dir" || !entry.main_file || files.length === 0) {
      return fail(400, "entry is held by reference — it has no page of its own to open");
    }
    // Fetch every file's exact bytes and hash them: the
    // tree digest keys the mirror, so any file's change
    // re-mirrors under a fresh prefix and a repeat open of
    // an unchanged tree puts nothing.
    const fetched: { path: string; bytes: Uint8Array; contentType: string }[] = [];
    const skipped: { path: string; reason: string }[] = [];
    for (const file of files) {
      const rawPath =
        `/raw/${enc(args.slug)}/entries/${enc(args.entryId)}/` +
        file.path.split("/").map(enc).join("/");
      const raw = await callServerRaw(ctx, rawPath);
      if (raw.status === 0) {
        return fail(0, "companion server did not answer the byte route in time");
      }
      const bytes = base64ToBytes(raw.bodyBase64);
      if (raw.status !== 200) {
        const note =
          new TextDecoder().decode(bytes).trim() || `byte route refused the file (${raw.status})`;
        if (file.is_main) return fail(raw.status, note);
        skipped.push({ path: file.path, reason: note });
        continue;
      }
      fetched.push({
        path: file.path,
        bytes,
        contentType: raw.contentType ?? "application/octet-stream",
      });
    }
    const parts: string[] = [];
    for (const file of fetched) parts.push(`${file.path}\0${await sha256Hex(file.bytes)}\n`);
    const digest = await sha256Hex(parts.sort().join(""));
    const prefix = `entries/${args.slug}/${args.entryId}/${digest.slice(0, 16)}`;
    for (const file of fetched) {
      const key = `${prefix}/${file.path}`;
      const existing = await ctx.blobs.head(key).catch(() => null);
      if (existing == null) {
        await ctx.blobs.put(key, file.bytes, {
          contentType: file.contentType,
          public: true,
        });
      }
    }
    const url = await ctx.blobs.getUrl(`${prefix}/${entry.main_file}`, { public: true });
    return {
      status: 200,
      payload: {
        url,
        verified_at: new Date().toISOString(),
        files: fetched.length,
        digest: digest.slice(0, 16),
        skipped,
      },
      error: null,
    };
  },
});
