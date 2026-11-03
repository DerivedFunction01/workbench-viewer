// Shared highlight.js access for every code surface
// (the repo peek + editor, the plan source view, the
// changes panel, the diff views). Before this module each
// surface lazy-loaded the chunk itself behind a thin
// extension map, so unmapped files rendered plain; here
// the map is completed once, unmapped content gets a
// highlightAuto fallback behind a relevance floor, and
// the load is cached and never throws — a failed load or
// an unknown language resolves null and the caller
// renders plain text, never a hole. The colors live in
// themes/highlight.css (the palettes' semantic roles);
// this module produces markup only.

import type { HLJSApi } from "highlight.js";

/** highlightAuto guesses below this relevance are not
 * trusted: short or prose-like content scores low and a
 * wrong-language highlight is worse than plain text.
 * Real code — even a few lines — scores well above it. */
export const AUTO_RELEVANCE_FLOOR = 10;

const EXT_TO_LANGUAGE: Record<string, string> = {
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  py: "python",
  pyw: "python",
  md: "markdown",
  markdown: "markdown",
  json: "json",
  jsonc: "json",
  css: "css",
  scss: "scss",
  less: "less",
  html: "xml",
  htm: "xml",
  xml: "xml",
  svg: "xml",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  yaml: "yaml",
  yml: "yaml",
  // highlight.js has no TOML grammar; its INI grammar
  // registers "toml" as an alias and is the stand-in.
  toml: "ini",
  rs: "rust",
  go: "go",
  sql: "sql",
  c: "c",
  h: "cpp",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  hh: "cpp",
  hpp: "cpp",
  hxx: "cpp",
  java: "java",
  rb: "ruby",
  php: "php",
  r: "r",
  lua: "lua",
  kt: "kotlin",
  kts: "kotlin",
  swift: "swift",
  cs: "csharp",
  pl: "perl",
  pm: "perl",
  hs: "haskell",
  ex: "elixir",
  exs: "elixir",
  erl: "erlang",
  clj: "clojure",
  dart: "dart",
  scala: "scala",
  groovy: "groovy",
  diff: "diff",
  patch: "diff",
  // Datasets are data, not code: a deliberate plaintext
  // mapping so they never pick up a wrong auto-detect.
  csv: "plaintext",
  tsv: "plaintext",
  txt: "plaintext",
};

const FILENAME_TO_LANGUAGE: Record<string, string> = {
  dockerfile: "dockerfile",
  containerfile: "dockerfile",
  makefile: "makefile",
  gnumakefile: "makefile",
  "cmakelists.txt": "cmake",
  rakefile: "ruby",
  gemfile: "ruby",
  vagrantfile: "ruby",
  jenkinsfile: "groovy",
};

/** The language a path declares, by filename first,
 * then extension. Undefined when the path names no
 * language (extensionless files, dotfiles, data) — the
 * caller's fallback decides what happens then. */
export function languageForPath(path: string): string | undefined {
  const base = path.split("/").pop()?.toLowerCase() ?? "";
  const byName = FILENAME_TO_LANGUAGE[base];
  if (byName) return byName;
  if (base === "dockerfile" || base.startsWith("dockerfile.")) return "dockerfile";
  const dot = base.lastIndexOf(".");
  if (dot <= 0) return undefined;
  return EXT_TO_LANGUAGE[base.slice(dot + 1)];
}

let hljsPromise: Promise<HLJSApi | null> | null = null;

function loadHljs(): Promise<HLJSApi | null> {
  if (!hljsPromise) {
    hljsPromise = import("highlight.js").then((m) => m.default).catch(() => null);
  }
  return hljsPromise;
}

/** The language to highlight `content` with: the path's
 * mapped language when the bundle has it, else the
 * highlightAuto guess when it clears the relevance
 * floor, else null (render plain). */
export async function detectLanguage(content: string, path?: string): Promise<string | null> {
  const hljs = await loadHljs();
  if (!hljs) return null;
  try {
    const mapped = path ? languageForPath(path) : undefined;
    if (mapped && hljs.getLanguage(mapped)) return mapped;
    const auto = hljs.highlightAuto(content);
    if (auto.language && auto.relevance >= AUTO_RELEVANCE_FLOOR) {
      return auto.language;
    }
    return null;
  } catch {
    return null;
  }
}

/** Highlight with an explicit language. Null when the
 * bundle lacks the language or anything fails. */
export async function highlightWithLanguage(
  content: string,
  language: string,
): Promise<string | null> {
  const hljs = await loadHljs();
  if (!hljs) return null;
  try {
    if (!hljs.getLanguage(language)) return null;
    return hljs.highlight(content, { language }).value;
  } catch {
    return null;
  }
}

/** Highlight whole content: the path's mapped language,
 * else the auto-detect fallback, else null (plain). */
export async function highlightCode(content: string, path?: string): Promise<string | null> {
  const language = await detectLanguage(content, path);
  if (!language) return null;
  return highlightWithLanguage(content, language);
}

/** Highlight lines independently (the diff views: a
 * construct spanning lines loses its tail coloring, the
 * accepted per-line trade). The language is detected
 * once over the joined text, so a single odd line never
 * picks its own grammar. Returns one entry per input
 * line (null = render that line plain), or null when no
 * language could be detected at all. */
export async function highlightLines(
  texts: string[],
  path?: string,
): Promise<(string | null)[] | null> {
  if (texts.length === 0) return [];
  const language = await detectLanguage(texts.join("\n"), path);
  if (!language) return null;
  const out: (string | null)[] = [];
  for (const text of texts) {
    out.push(await highlightWithLanguage(text, language));
  }
  return out;
}
