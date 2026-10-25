// STUB — Subplan 03 scaffold. Typed actions over the raw-socket bridge
// land in Subplan 05 (with server/src/privileged.ts); this single ping
// action only proves the server builds and typechecks end to end.
import { type ActionsModule, defineAction, z } from "@hatch/space-sdk";

export const Actions = {
  ping: defineAction({
    request: z.object({}),
    response: z.object({ ok: z.boolean() }),
    async handler() {
      return { ok: true };
    },
  }),
} satisfies ActionsModule;
