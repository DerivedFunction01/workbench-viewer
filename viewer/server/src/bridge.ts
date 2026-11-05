// The proxy core: one bridge attempt to the companion
// server over the privileged wbApi socket contract, plus
// the retry policy that turns on how the attempt died.
// A timeout means the server is up but busy (no retry —
// a second attempt doubles the load it is drowning in);
// a connection that never reached the server earns one
// retry for reads (the mid-restart transient). Writes
// are never retried. Split from actions.ts by intent
// (2026-11-05 contracts-blockers program): the actions
// file carries the action set; this module carries the
// bridge they all ride.
import type { Ctx } from "@hatch/space-sdk";
import { privileged } from "@space/privileged";
import { companionAddress, unreachableMessage } from "./config";

// ---------------------------------------------------------------------------
// The proxy core
// ---------------------------------------------------------------------------

// The payload is the server's body verbatim; T is the
// action's declared payload type (its looseObject schema is
// the contract the server's shape is checked against at the
// action boundary).
export interface BridgeReply<T> {
  status: number;
  payload: T | null;
  error: string | null;
}

// One bridge attempt, plus whether it died on the socket
// timeout: callServer's retry policy turns on that
// distinction (a timeout and a refused connection are
// opposite diagnoses — busy server vs restarting server).
interface BridgeAttempt<T> {
  reply: BridgeReply<T>;
  timedOut: boolean;
}

async function callServerOnce<T>(
  ctx: Ctx,
  path: string,
  method: "GET" | "POST",
  body?: unknown,
): Promise<BridgeAttempt<T>> {
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
    // A bridge timeout is not "unreachable": the server is
    // up but slow (its log shows the answer dying on a
    // broken pipe after the reader gave up). Say which one
    // happened so a slow server is never reported as down.
    if (serverError?.startsWith("timed out")) {
      return {
        timedOut: true,
        reply: {
          status: 0,
          payload: null,
          error:
            `Companion server on ${address.host}:${address.port} did not answer in time — ` +
            "it is running but busy.",
        },
      };
    }
    return {
      timedOut: false,
      reply: { status: 0, payload: null, error: unreachableMessage(address) },
    };
  }
  if (serverError != null) {
    return { timedOut: false, reply: { status: res.status, payload: null, error: serverError } };
  }
  return { timedOut: false, reply: { status: res.status, payload: json as T, error: null } };
}

export async function callServer<T>(
  ctx: Ctx,
  path: string,
  method: "GET" | "POST" = "GET",
  body?: unknown,
): Promise<BridgeReply<T>> {
  const first = await callServerOnce<T>(ctx, path, method, body);
  if (first.reply.status !== 0 || method !== "GET") return first.reply;
  // A timeout earns NO retry (2026-10-31, second lesson):
  // the server is busy computing the very feed that just
  // timed out, so a second attempt doubles its load — and
  // two 20s socket timeouts stacked inside one action blow
  // straight past the privileged contract's 30s cap, so
  // the platform tears the call down mid-retry and the
  // client's query never settles into either data or an
  // error: every section sits on its loading skeleton
  // (Settings included — its fast feed queues behind the
  // same wedged calls). Return the "busy" envelope at
  // once; the section renders it as a named error with a
  // reload path, which is the truth.
  if (first.timedOut) return first.reply;
  // One retry for reads whose first attempt never reached
  // the server: the transient case — the server
  // mid-restart, its socket not yet accepting. The client
  // caches an error envelope with no automatic retry of
  // its own, so without this a seconds-long blip became a
  // permanent "unreachable" well on every section
  // (2026-10-31). Writes are never retried: a save whose
  // answer was lost may already have landed, and its
  // compare-and-swap base would be stale.
  const second = await callServerOnce<T>(ctx, path, method, body);
  return second.reply;
}
