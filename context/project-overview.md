# Workbench Viewer

## Overview

The Workbench Viewer is the workspace's single surface for
design state and work state. A vibe-coded project accumulates
scattered mockup artifacts, plan files, and loose to-dos until
nobody knows which mockup is canonical, which plan is in
flight, or what is blocked. This harness fixes that by
structure: one always-on companion server reads every opt-in
project's own data files and serves one artifact with four
sections — Mockups, Plans, Todos, Board. It is a general
harness, not a component of any one project: a new repo adopts
it by adding one small manifest file.

## Goals

1. Any question of the form "which mockup is canonical, what's
   deferred, what's stale, what's a hard gate — in any project"
   is answerable from the viewer alone.
2. Adoption cost for a new repo is one tracked file
   (`workbench.yaml`) and zero code.
3. Mockup review happens in the viewer — approve /
   needs-changes / stale, with a comment log — so design
   feedback never travels as chat paste-back.
4. Plans read better in the viewer than as raw files:
   formatted, structured, with Mermaid diagrams drawn.

## Core User Flow

1. the owner opens the Workbench Viewer artifact.
2. The artifact asks the companion server (loopback, raw
   socket) for the swept project list and the section feeds.
3. In Mockups he works the triage lane: entries awaiting
   review, stale badges with reasons, drift flags.
4. He edits a mockup's internal state live, watches it
   re-render, then approves — the approval records the exact
   state snapshot it covers.
5. In Plans he reads any project's plans formatted, diagrams
   rendered; in Todos and on the Board he sees what is in
   progress across projects.
6. Anything he changes lands through the same lib/ mutations
   the `wb` CLI uses — one audit history per entry.

## Features

### Mockups

- Per-project registry browser: ruled status chip + derived
  stale badge per entry, filters, archive behind a toggle.
- Review dispositions (approve / needs-changes / mark-stale)
  with an append-only comment log per entry.
- Internal-state controls rendered from each entry's declared
  state schema; approval bound to the state snapshot.
- Guarded file peek/save (sha-checked, off by default).

### Plans

- Formatted rendering of each project's `.plans/`: header
  fields and step blocks structured; finished plans in an
  archive view; Mermaid fences rendered as diagrams (lazy,
  with source fallback); non-conforming plans rendered whole
  as formatted markdown — the parser never drops content.

### Todos

- Per project and cross-project; stored in each project's
  registry DB; add/edit/complete in the viewer or via `wb`.

### Board

- Kanban view over three sources: todos (draggable; a drag is
  a todo-status mutation), plan cards placed by plan header
  status (derived, read-only), and the mockup review queue.

## Scope

### In Scope

- The harness: lib/, `wb` CLI, companion server, the artifact.
- Projects in this workspace that carry a manifest.

### Out of Scope

- another-project — excluded by design (own maintenance system,
  external to this workspace).
- Project *data* of any other kind: no pay figures, no repo
  browsing (that is the git repo viewer's job), no dashboards.
- Scheduling the staleness check (a platform concern; `wb
  print-schedule` only emits the definition).

## Success Criteria

1. Two projects (this repo as project zero, example-project-legacy
   v2) are clients of the harness, and both provably build and
   test with it absent.
2. The full mockup lifecycle (add → canonical-with-ruling →
   supersede → archive → verify) runs from the CLI alone, and
   the same actions work from the viewer.
3. The published viewer reaches its server through the
   artifact's socket path, and the server is boring: always
   up, per-project failures contained to that project's feed.
