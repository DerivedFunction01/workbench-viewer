// The shared react-query keys, named once here instead
// of hand-rolled per call site (contracts audit,
// 2026-11-05). Only keys that more than one surface
// reads or invalidates live here; a section's private
// keys stay in its section.
//
// The literal values are the contract: invalidation
// matches by key prefix, so a key's shape must not
// change when a call site migrates to this module —
// e.g. the shell's triage keys are ["entries", slug]
// (two elements) while the Entries section's own feed
// keys are ["entries", slug, archived] (three); both
// shapes are live, and the section's stay literal there.

export const projectsKey = ["projects"] as const;
export const healthKey = ["health"] as const;
export const homeKey = ["home"] as const;
export const configKey = ["config"] as const;

export const boardKey = (slug: string) => ["board", slug] as const;
export const plansKey = (slug: string) => ["plans", slug] as const;
export const todosKey = (slug: string) => ["todos", slug] as const;

// The shell's per-project triage key (see the header
// note on shapes).
export const entriesKey = (slug: string | undefined) => ["entries", slug] as const;

// Message keys carry their filters as trailing parts:
// ["messages"], ["messages", project],
// ["messages", "", "sent"] are all live shapes.
export const messagesKey = (...parts: string[]) => ["messages", ...parts] as const;

// Root keys for prefix invalidation: invalidating the
// root invalidates every key under it.
export const boardRootKey = ["board"] as const;
export const plansRootKey = ["plans"] as const;
export const todosRootKey = ["todos"] as const;
export const messagesRootKey = ["messages"] as const;
