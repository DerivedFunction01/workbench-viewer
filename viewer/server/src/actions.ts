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
import { type ActionsModule, type Ctx, defineAction, z } from "@hatch/space-sdk";
import { privileged } from "@space/privileged";
import { companionAddress, unreachableMessage } from "./config";

// ---------------------------------------------------------------------------
// Payload schemas (loose: the server's fields, verbatim + typed where known)
// ---------------------------------------------------------------------------

const projectSections = z.looseObject({
  mockups: z.boolean(),
  artifacts: z.boolean(),
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

// ---------------------------------------------------------------------------
// The proxy core
// ---------------------------------------------------------------------------

// The payload is the server's body verbatim; T is the
// action's declared payload type (its looseObject schema is
// the contract the server's shape is checked against at the
// action boundary).
interface BridgeReply<T> {
  status: number;
  payload: T | null;
  error: string | null;
}

async function callServer<T>(
  ctx: Ctx,
  path: string,
  method: "GET" | "POST" = "GET",
  body?: unknown,
): Promise<BridgeReply<T>> {
  const address = companionAddress();
  const res = await ctx.executePrivileged(privileged.wbApi, {
    host: address.host,
    port: address.port,
    method,
    path,
    body: body != null ? JSON.stringify(body) : null,
  });
  const json = res.json;
  const obj = json != null && typeof json === "object" ? (json as Record<string, unknown>) : null;
  const serverError = obj && typeof obj.error === "string" ? obj.error : null;
  if (res.status === 0) {
    return { status: 0, payload: null, error: unreachableMessage(address) };
  }
  if (serverError != null) {
    return { status: res.status, payload: null, error: serverError };
  }
  return { status: res.status, payload: json as T, error: null };
}

const slugArg = z.object({ slug: z.string().min(1) });
const entryArg = z.object({ slug: z.string().min(1), entryId: z.string().min(1) });

const enc = encodeURIComponent;

// ---------------------------------------------------------------------------
// Actions — one per companion-server route (SPEC §7)
// ---------------------------------------------------------------------------

export const Actions = {
  getHealth: defineAction({
    request: z.object({}),
    response: healthResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof healthPayload>>(ctx, "/api/health");
    },
  }),

  getConfig: defineAction({
    request: z.object({}),
    response: configResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof configResult>["payload"]>(ctx, "/api/config");
    },
  }),

  listProjects: defineAction({
    request: z.object({}),
    response: projectsResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof projectsPayload>>(ctx, "/api/projects");
    },
  }),

  rescanProjects: defineAction({
    request: z.object({}),
    response: projectsResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<z.infer<typeof projectsPayload>>(ctx, "/api/projects/rescan", "POST", {});
    },
  }),

  getMockups: defineAction({
    request: z.object({ slug: z.string().min(1), archived: z.boolean().optional() }),
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const suffix = args.archived ? "?archived=1" : "";
      return callServer<z.infer<typeof feedEnvelope>>(
        ctx,
        `/api/projects/${enc(args.slug)}/mockups${suffix}`,
      );
    },
  }),

  getArtifacts: defineAction({
    request: z.object({ slug: z.string().min(1), archived: z.boolean().optional() }),
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      const suffix = args.archived ? "?archived=1" : "";
      return callServer<z.infer<typeof feedEnvelope>>(
        ctx,
        `/api/projects/${enc(args.slug)}/artifacts${suffix}`,
      );
    },
  }),

  getEntry: defineAction({
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

  entryAction: defineAction({
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
    request: slugArg,
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<z.infer<typeof feedEnvelope>>(ctx, `/api/projects/${enc(args.slug)}/plans`);
    },
  }),

  getPlan: defineAction({
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
    request: slugArg,
    response: feedResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<z.infer<typeof feedEnvelope>>(ctx, `/api/projects/${enc(args.slug)}/todos`);
    },
  }),

  getAllTodos: defineAction({
    request: z.object({}),
    response: proxied(z.looseObject({ todos: z.array(z.unknown()) })),
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<{ todos: unknown[] }>(ctx, "/api/todos");
    },
  }),

  todoAction: defineAction({
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

  getBoard: defineAction({
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/board");
    },
  }),

  // -- repo-home additions (repo-home spec §§3-7, §15, §17):
  // the /api namespace, proxied verbatim like everything
  // above. Payloads ride rawResult: their shapes are the
  // home/messages/settings contracts in lib/, typed on the
  // client in lib/api.ts.
  getHome: defineAction({
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/home");
    },
  }),

  getWorktrees: defineAction({
    request: slugArg,
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/projects/${enc(args.slug)}/worktrees`);
    },
  }),

  getEffectiveSettings: defineAction({
    request: z.object({}),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx) {
      return callServer<unknown>(ctx, "/api/settings/effective");
    },
  }),

  getMessages: defineAction({
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
    request: z.object({ body: z.record(z.string(), z.unknown()) }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, "/api/messages", "POST", args.body);
    },
  }),

  sendMessage: defineAction({
    request: z.object({ id: z.number().int() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/send`, "POST", {});
    },
  }),

  doneMessage: defineAction({
    request: z.object({ id: z.number().int() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/done`, "POST", {});
    },
  }),

  archiveMessage: defineAction({
    request: z.object({ id: z.number().int() }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, `/api/messages/${args.id}/archive`, "POST", {});
    },
  }),

  cleanupMessages: defineAction({
    request: z.object({ body: z.record(z.string(), z.unknown()) }),
    response: rawResult,
    privileged: [privileged.wbApi],
    async handler(ctx, args) {
      return callServer<unknown>(ctx, "/api/messages/cleanup", "POST", args.body);
    },
  }),
} satisfies ActionsModule;
