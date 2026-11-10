// Typed actions over the raw-socket bridge — a THIN proxy
// (Subplan 05, Step 2). Each action forwards exactly one
// feed/mutation call to the companion server through the
// privileged wbApi socket contract and returns the server's
// payload verbatim: payload schemas are looseObjects (known
// fields typed, everything else carried through untouched),
// the HTTP status rides along, and a server `{error}` body —
// or an unreachable server — comes back in the same envelope
// shape, never as a hang or a thrown exception. The bridge
// is boring on purpose: errors pass through with their
// shape intact (SPEC §7 conventions: 400/403/404/409/413).
import { type ActionsModule, defineAction, z } from "@hatch/space-sdk";
import { privileged } from "@space/privileged";
import { callServer } from "./bridge";
import { getEntryPage } from "./page";

// ---------------------------------------------------------------------------
// Payload schemas (loose: the server's fields, verbatim + typed where known)
// ---------------------------------------------------------------------------

const projectSections = z.looseObject({
  entries: z.boolean(),
  todos: z.boolean(),
  plans: z.boolean(),
  registry_declared: z.boolean(),
  plans_declared: z.boolean(),
});

const projectSummary = z.looseObject({
  slug: z.string(),
  name: z.string(),
  root: z.string(),
  sections: projectSections,
});

const healthPayload = z.looseObject({
  ok: z.boolean(),
  version: z.string(),
  host: z.string(),
  port: z.number(),
  projects_count: z.number(),
});

const projectsPayload = z.looseObject({
  projects: z.array(projectSummary),
  errors: z.array(z.unknown()),
});

const feedEnvelope = z.looseObject({
  slug: z.string(),
  name: z.string(),
  degraded: z.boolean(),
  available: z.boolean(),
});

// One envelope for every proxied call: the HTTP status (0 =
// the socket never got an answer), the payload verbatim, and
// the server's error string when it sent one.
const proxied = <T extends z.ZodType>(payload: T) =>
  z.object({
    status: z.number(),
    payload: payload.nullable(),
    error: z.string().nullable(),
  });

const healthResult = proxied(healthPayload);
const projectsResult = proxied(projectsPayload);
const configResult = proxied(z.looseObject({ config: z.record(z.string(), z.unknown()) }));
const feedResult = proxied(feedEnvelope);
const rawResult = proxied(z.unknown());

export type HealthResult = z.infer<typeof healthResult>;
export type ProjectsResult = z.infer<typeof projectsResult>;
export type ConfigResult = z.infer<typeof configResult>;
export type FeedResult = z.infer<typeof feedResult>;
export type RawResult = z.infer<typeof rawResult>;

const slugArg = z.object({ slug: z.string().min(1) });
const entryArg = z.object({ slug: z.string().min(1), entryId: z.string().min(1) });
const repoArg = z.object({ repoId: z.string().min(1) });

const enc = encodeURIComponent;

// Repo ids are workspace-relative paths and may contain
// slashes: each segment is encoded, the slashes ride
// through (the server joins the trailing segments back
// into the id).
const encRepoId = (id: string) => id.split("/").map(enc).join("/");

// ---------------------------------------------------------------------------
// Actions — one per companion-server route (SPEC §7)
// ---------------------------------------------------------------------------

export const Actions = {
  getHealth: defineAction({
    description:
      "Check whether the companion server is up and report its version and project count.",
    request: z.object({}),
    response: healthResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof healthPayload>>(ctx, "/api/health");
    },
  }),

  getConfig: defineAction({
    description: "Fetch the companion server's public configuration.",
    request: z.object({}),
    response: configResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof configResult>["payload"]>(ctx, "/api/config");
    },
  }),

  listProjects: defineAction({
    description: "List the projects in the companion server's sweep.",
    request: z.object({}),
    response: projectsResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof projectsPayload>>(ctx, "/api/projects");
    },
  }),

  rescanProjects: defineAction({
    description:
      "Ask the companion server to rescan the workspace and return the updated project list.",
    request: z.object({}),
    response: projectsResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof projectsPayload>>(ctx, "/api/projects/rescan", "POST", {});
    },
  }),

  // Manual refresh (cache-refresh plan, design point 5):
  // busts the companion's sweep + feed caches server-side;
  // the client then invalidates every query so the whole
  // shell re-reads fresh.
  forceRefresh: defineAction({
    description:
      "Force-refresh all viewer data: bust the companion server's sweep and feed caches so every feed re-derives from disk.",
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/refresh", "POST", {});
    },
  }),

  getEntries: defineAction({
    description: "Fetch one project's entries feed, optionally including archived entries.",
    request: z.object({ slug: z.string().min(1), archived: z.boolean().optional() }),
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const suffix = args.archived ? "?archived=1" : "";
      return callServer<z.infer<typeof feedEnvelope>>(
        ctx,
        `/api/projects/${enc(args.slug)}/entries${suffix}`,
      );
    },
  }),

  getEntry: defineAction({
    description: "Fetch one entry's detail, files, and history.",
    request: entryArg,
    // The entry-detail payload ({entry, files, history,
    // latest_review, approval, derived}) is NOT a feed
    // envelope — it carries no slug/name/degraded/available —
    // so it passes through verbatim like getEntryFile.
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(
        ctx,
        `/api/projects/${enc(args.slug)}/entries/${enc(args.entryId)}`,
      );
    },
  }),

  getEntryFile: defineAction({
    description: "Read one file of an entry, optionally revealing a withheld secret-shaped file.",
    request: z.object({
      slug: z.string().min(1),
      entryId: z.string().min(1),
      path: z.string().optional(),
      reveal: z.boolean().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      if (args.path) params.set("path", args.path);
      if (args.reveal) params.set("reveal", "1");
      const query = params.toString();
      const suffix = query ? `?${query}` : "";
      return callServer<unknown>(
        ctx,
        `/api/projects/${enc(args.slug)}/entries/${enc(args.entryId)}/file${suffix}`,
      );
    },
  }),

  saveEntryFile: defineAction({
    description:
      "Save an edited entry file through the companion server with compare-and-swap protection.",
    request: z.object({
      slug: z.string().min(1),
      entryId: z.string().min(1),
      path: z.string().min(1),
      content: z.string(),
      baseSha256: z.string().min(1),
      confirmSecret: z.boolean().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer(
        ctx,
        `/api/projects/${enc(args.slug)}/entries/${enc(args.entryId)}/file`,
        "POST",
        {
          path: args.path,
          content: args.content,
          base_sha256: args.baseSha256,
          confirm_secret: args.confirmSecret === true,
        },
      );
    },
  }),

  // The in-viewer render's action (page.ts): the one
  // action that is not a proxy of one companion route.
  getEntryPage,

  entryAction: defineAction({
    description: "Run a lifecycle action such as review, approve, or archive on an entry.",
    request: z.object({
      slug: z.string().min(1),
      entryId: z.string().min(1),
      body: z.record(z.string(), z.unknown()),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer(
        ctx,
        `/api/projects/${enc(args.slug)}/entries/${enc(args.entryId)}/action`,
        "POST",
        args.body,
      );
    },
  }),

  getPlans: defineAction({
    description: "Fetch one project's plans and bundles feed.",
    request: slugArg,
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<z.infer<typeof feedEnvelope>>(ctx, `/api/projects/${enc(args.slug)}/plans`);
    },
  }),

  getPlan: defineAction({
    description: "Fetch one plan document's structured content.",
    request: z.object({ slug: z.string().min(1), path: z.string().min(1) }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(
        ctx,
        `/api/projects/${enc(args.slug)}/plan?path=${enc(args.path)}`,
      );
    },
  }),

  resolvePlanQuestions: defineAction({
    description: "Record answers to a plan's open questions back into the plan file.",
    request: z.object({
      slug: z.string().min(1),
      path: z.string().min(1),
      baseSha256: z.string().min(1),
      answers: z.record(z.string(), z.string()),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/projects/${enc(args.slug)}/plan/resolve`, "POST", {
        path: args.path,
        base_sha256: args.baseSha256,
        answers: args.answers,
      });
    },
  }),

  getProjectTodos: defineAction({
    description: "Fetch one project's todo feed.",
    request: slugArg,
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<z.infer<typeof feedEnvelope>>(ctx, `/api/projects/${enc(args.slug)}/todos`);
    },
  }),

  todoAction: defineAction({
    description: "Create, update, or complete a todo in one project.",
    request: z.object({
      slug: z.string().min(1),
      body: z.record(z.string(), z.unknown()),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer(ctx, `/api/projects/${enc(args.slug)}/todos`, "POST", args.body);
    },
  }),

  getDiff: defineAction({
    description: "Fetch the anchored diff for one project's worktree, bundle, or commit.",
    request: z.object({
      slug: z.string().min(1),
      worktree: z.string().optional(),
      mode: z.string().optional(),
      base: z.string().optional(),
      target: z.string().optional(),
      bundle: z.string().optional(),
      all: z.boolean().optional(),
      peek: z.string().optional(),
    }),
    // The diff payload is its own shape (§18.5), not a
    // feed envelope — verbatim, like getPlan.
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      if (args.worktree) params.set("worktree", args.worktree);
      if (args.mode) params.set("mode", args.mode);
      if (args.base) params.set("base", args.base);
      if (args.target) params.set("target", args.target);
      if (args.bundle) params.set("bundle", args.bundle);
      if (args.all) params.set("all", "1");
      if (args.peek) params.set("peek", args.peek);
      const query = params.toString();
      const suffix = query ? `?${query}` : "";
      return callServer<unknown>(ctx, `/api/projects/${enc(args.slug)}/diff${suffix}`);
    },
  }),

  // One project's board portion (heavy-feed batching):
  // card projections with the done lanes paginated —
  // the board screen assembles portions client-side.
  getBoardProject: defineAction({
    description: "Fetch one project's board portion: card projections with paginated done lanes.",
    request: z.object({
      slug: z.string(),
      doneOffset: z.number().int().min(0).optional(),
      doneLimit: z.number().int().min(1).max(500).optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      if (args.doneOffset !== undefined) {
        params.set("done_offset", String(args.doneOffset));
      }
      if (args.doneLimit !== undefined) {
        params.set("done_limit", String(args.doneLimit));
      }
      const query = params.toString();
      const suffix = query ? `?${query}` : "";
      return callServer<unknown>(ctx, `/api/projects/${enc(args.slug)}/board${suffix}`);
    },
  }),

  // -- repo-home additions (repo-home spec §§3-7, §15, §17):
  // the /api namespace, proxied verbatim like everything
  // above. Payloads ride rawResult: their shapes are the
  // home/messages/settings contracts in lib/, typed on the
  // client in lib/api-types.ts.
  getHome: defineAction({
    description: "Fetch the workspace home feed with per-project status summaries.",
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/home");
    },
  }),

  getWorktrees: defineAction({
    description: "Fetch one project's git worktrees with their derivations.",
    request: slugArg,
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/projects/${enc(args.slug)}/worktrees`);
    },
  }),

  getEffectiveSettings: defineAction({
    description: "Fetch the companion server's effective settings and message-store status.",
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/settings/effective");
    },
  }),

  getMessages: defineAction({
    description: "Fetch inbox messages, optionally filtered by project, state, anchor, or pickup.",
    request: z.object({
      project: z.string().optional(),
      state: z.string().optional(),
      anchorType: z.string().optional(),
      anchorRef: z.string().optional(),
      pickup: z.boolean().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      if (args.project) params.set("project", args.project);
      if (args.state) params.set("state", args.state);
      if (args.anchorType) params.set("anchor_type", args.anchorType);
      if (args.anchorRef) params.set("anchor_ref", args.anchorRef);
      if (args.pickup) params.set("pickup", "1");
      const query = params.toString();
      return callServer<unknown>(ctx, `/api/messages${query ? `?${query}` : ""}`);
    },
  }),

  updateMessageBody: defineAction({
    description: "Replace the body of one inbox message.",
    request: z.object({ id: z.number().int(), body: z.string() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/body`, "POST", {
        body: args.body,
      });
    },
  }),

  createMessage: defineAction({
    description: "Create a new inbox message or annotation.",
    request: z.object({ body: z.record(z.string(), z.unknown()) }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, "/api/messages", "POST", args.body);
    },
  }),

  sendMessage: defineAction({
    description: "Send one drafted inbox message.",
    request: z.object({ id: z.number().int() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/send`, "POST", {});
    },
  }),

  doneMessage: defineAction({
    description: "Mark one inbox message as done.",
    request: z.object({ id: z.number().int() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/done`, "POST", {});
    },
  }),

  archiveMessage: defineAction({
    description: "Archive one inbox message.",
    request: z.object({ id: z.number().int() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/archive`, "POST", {});
    },
  }),

  cleanupMessages: defineAction({
    description: "Run the inbox cleanup policy over old messages.",
    request: z.object({ body: z.record(z.string(), z.unknown()) }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, "/api/messages/cleanup", "POST", args.body);
    },
  }),

  // -- repos (absorption plan, steps 8-9): the workspace
  // repo census, per-repo status / files / peek / save /
  // history, and the repo registry. Payloads ride
  // rawResult: their shapes are the lib/repos.py,
  // lib/files.py, lib/repo_state.py contracts, typed on
  // the client in lib/api-types-repos.ts.
  getRepos: defineAction({
    description: "Fetch the workspace repo census with sync and exposure summaries.",
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/repos");
    },
  }),

  getRepoStatus: defineAction({
    description: "Fetch one repo's detailed git status, commits, and branches.",
    request: repoArg,
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/repos/${encRepoId(args.repoId)}/status`);
    },
  }),

  getRepoFiles: defineAction({
    description: "List one directory of a repo's file tree, or the full tree, for the Files view.",
    request: z.object({
      repoId: z.string().min(1),
      all: z.boolean().optional(),
      dir: z.string().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      if (args.dir != null) params.set("dir", args.dir);
      else if (args.all) params.set("all", "1");
      const query = params.toString();
      const suffix = query ? `?${query}` : "";
      return callServer<unknown>(ctx, `/api/repos/${encRepoId(args.repoId)}/files${suffix}`);
    },
  }),

  getRepoFile: defineAction({
    description:
      "Read one repo file for the peek and editor, optionally revealing a withheld secret-shaped file.",
    request: z.object({
      repoId: z.string().min(1),
      path: z.string().min(1),
      reveal: z.boolean().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      params.set("path", args.path);
      if (args.reveal) params.set("reveal", "1");
      return callServer<unknown>(
        ctx,
        `/api/repos/${encRepoId(args.repoId)}/file?${params.toString()}`,
      );
    },
  }),

  saveRepoFile: defineAction({
    description:
      "Save an edited repo file with compare-and-swap protection, preserving its permissions.",
    request: z.object({
      repoId: z.string().min(1),
      path: z.string().min(1),
      content: z.string(),
      baseSha256: z.string().min(1),
      confirmSecret: z.boolean().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/repos/${encRepoId(args.repoId)}/file`, "POST", {
        path: args.path,
        content: args.content,
        base_sha256: args.baseSha256,
        confirm_secret: args.confirmSecret === true,
      });
    },
  }),

  // -- datasets (peek-highlight-and-datasets plan, steps
  // 5-6): the Table view over dataset-kind repo files —
  // described schema, one bounded rows page, on-demand
  // column stats, and the guarded SQL console. Shapes are
  // the lib/datasets/derivations.py + console.py
  // contracts, typed on the client in lib/api-types-repos.ts.
  getRepoDataset: defineAction({
    description: "Describe a dataset file's schema for the Table view.",
    request: z.object({
      repoId: z.string().min(1),
      path: z.string().min(1),
      table: z.string().min(1).optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      params.set("path", args.path);
      if (args.table) params.set("table", args.table);
      return callServer<unknown>(
        ctx,
        `/api/repos/${encRepoId(args.repoId)}/dataset?${params.toString()}`,
      );
    },
  }),

  getRepoDatasetRows: defineAction({
    description: "Fetch one bounded, sortable, filterable page of dataset rows.",
    request: z.object({
      repoId: z.string().min(1),
      path: z.string().min(1),
      table: z.string().min(1).optional(),
      limit: z.number().int().positive().optional(),
      offset: z.number().int().nonnegative().optional(),
      sort: z.string().min(1).optional(),
      dir: z.enum(["asc", "desc"]).optional(),
      filtersJson: z.string().optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      params.set("path", args.path);
      if (args.table) params.set("table", args.table);
      if (args.limit != null) params.set("limit", String(args.limit));
      if (args.offset != null) params.set("offset", String(args.offset));
      if (args.sort) params.set("sort", args.sort);
      if (args.dir) params.set("dir", args.dir);
      if (args.filtersJson) params.set("filters", args.filtersJson);
      return callServer<unknown>(
        ctx,
        `/api/repos/${encRepoId(args.repoId)}/dataset/rows?${params.toString()}`,
      );
    },
  }),

  getRepoDatasetStats: defineAction({
    description: "Compute on-demand column statistics for a dataset file.",
    request: z.object({
      repoId: z.string().min(1),
      path: z.string().min(1),
      table: z.string().min(1).optional(),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const params = new URLSearchParams();
      params.set("path", args.path);
      if (args.table) params.set("table", args.table);
      return callServer<unknown>(
        ctx,
        `/api/repos/${encRepoId(args.repoId)}/dataset/stats?${params.toString()}`,
      );
    },
  }),

  postRepoDatasetSql: defineAction({
    description: "Run one guarded read-only SQL query against a dataset file.",
    request: z.object({
      repoId: z.string().min(1),
      path: z.string().min(1),
      table: z.string().min(1).optional(),
      sql: z.string().min(1),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/repos/${encRepoId(args.repoId)}/dataset/sql`, "POST", {
        path: args.path,
        table: args.table,
        sql: args.sql,
      });
    },
  }),

  getRepoHistory: defineAction({
    description: "Fetch one repo's recorded status history and timeline.",
    request: repoArg,
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/repos/${encRepoId(args.repoId)}/history`);
    },
  }),

  getReposRegistry: defineAction({
    description: "Fetch the repo tracking registry the harness keeps for browsed repos.",
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/repos/registry");
    },
  }),

  updateReposRegistry: defineAction({
    description: "Update one entry of the repo tracking registry.",
    request: z.object({
      id: z.string().min(1),
      patch: z.record(z.string(), z.unknown()),
    }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, "/api/repos/registry", "POST", {
        id: args.id,
        patch: args.patch,
      });
    },
  }),
} satisfies ActionsModule;
