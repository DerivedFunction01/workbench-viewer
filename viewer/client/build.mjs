// Client bundle for the space — SCAFFOLD build (Subplan 03).
//
// The canonical artifact build is the SDK's buildClient()
// (@hatch/space-sdk/build), but that entry refuses to run outside the
// artifact builder pipeline (it publishes nothing by hand). This
// scaffold therefore bundles the same entrypoint with the same
// production settings directly via Bun.build, so the repo gate can
// prove the client compiles offline from a fresh checkout. The
// builder pipeline remains the only publish path; Subplan 05/08 may
// swap this shim for the SDK one when the shell lands.
//
// The Tailwind plugin is load-bearing, not decoration: without it
// the stylesheet ships the literal `@tailwind utilities;` directive
// and NO utility rules — every utility class in the kit (the
// Button's min-height, the coarse-pointer minimums) silently
// renders at UA defaults. The canonical build passes the same
// plugin (bun-plugin-tailwind, the SDK's own dependency); the
// scaffold matches it so a gate build renders what the published
// build renders. (Diagnosed 2026-11-10: the entries critic pass
// measured kit Buttons at 24–26px in harness builds for exactly
// this reason.)
import { rm } from "node:fs/promises";
import tailwindPlugin from "bun-plugin-tailwind";

const ENTRY = "./client/index.html";
const OUTDIR = "./client/dist";

if (typeof Bun === "undefined" || typeof Bun.build !== "function") {
  throw new Error("build.mjs must run under Bun");
}

await rm(OUTDIR, { force: true, recursive: true });
const result = await Bun.build({
  entrypoints: [ENTRY],
  outdir: OUTDIR,
  plugins: [tailwindPlugin],
  // Splitting keeps dynamic imports (mermaid, highlight.js)
  // as separate lazy chunks in the bundle — a page without
  // diagrams never loads the diagram chunk (Subplan 07).
  splitting: true,
  minify: true,
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  naming: {
    asset: "assets/[name]-[hash].[ext]",
    chunk: "assets/[name]-[hash].[ext]",
    entry: "[name].[ext]",
  },
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  throw new Error("client build failed; see logged diagnostics");
}
