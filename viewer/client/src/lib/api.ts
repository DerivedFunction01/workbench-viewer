// Typed client over the server actions (the git repo viewer's
// api.ts pattern): types come straight from
// `server/src/actions.ts` — no codegen. `import type` is
// load-bearing: the client bundle never pulls in server
// runtime, and `verbatimModuleSyntax` makes dropping `type`
// a compile error.
//
// Every action returns the bridge envelope
// `{ status, payload, error }`: `status` is the companion
// server's HTTP status (0 = unreachable over the socket),
// `payload` is the server's body verbatim, `error` its
// `{error}` string when it sent one. Sections read payloads
// through the feed types below; they never fetch directly —
// the only network this artifact touches is its own action
// channel to the privileged raw-socket bridge (SPEC §8).

import { createActionClient } from "@hatch/space-sdk/client";
import type { Actions } from "../../../server/src/actions";

export const api = createActionClient<typeof Actions>();

export type { ApiRequest, ApiResponse } from "@hatch/space-sdk/client";
