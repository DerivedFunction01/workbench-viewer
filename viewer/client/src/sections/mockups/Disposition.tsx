// The entry-action state (split from MockupDetail.tsx,
// 2026-11-05 follow-up): the entry-action mutation every
// write rides (a refusal is surfaced with the server's own
// reason) and the lifecycle form state the Lifecycle card
// renders. The review cluster that used to live here —
// the Disposition card, the approve confirm sheet, the
// review verbs — retired with the hosted byte route
// (2026-11-10): the kit page carries the answer contract
// now, and answers are recorded by transcription in the
// owning thread (SPEC §5.1). Recorded review history is
// untouched; it renders in the History and Review log
// cards like any other history rows.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Envelope, FullEntry } from "./types";

export function useDisposition({
  slug,
  entryId,
  entry,
  onMutated,
}: {
  slug: string;
  entryId: string;
  entry: FullEntry | null;
  onMutated: () => void;
}) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [statusChoice, setStatusChoice] = useState("canonical");
  const [ruling, setRuling] = useState("");
  const [gate, setGate] = useState("");
  const [acceptDrift, setAcceptDrift] = useState(false);
  const [supersedeTarget, setSupersedeTarget] = useState("");

  useEffect(() => {
    if (entry) {
      setStatusChoice(entry.status);
    }
  }, [entry]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["entry", slug, entryId] });
    queryClient.invalidateQueries({ queryKey: ["mockups", slug] });
    onMutated();
  };

  const actionMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.entryAction({ slug, entryId, body }) as Promise<Envelope>,
    onSuccess: (result, body) => {
      if (result.status === 200) {
        setActionError(null);
        setActionNotice(`Recorded — ${String(body.verb)} applied to ${entryId}.`);
        if (result.payload) {
          queryClient.setQueryData(["entry", slug, entryId], {
            status: 200,
            payload: result.payload,
            error: null,
          });
        }
        invalidate();
      } else {
        // The refusal IS the result: surface the server's reason.
        setActionNotice(null);
        setActionError(result.error ?? `The server refused this action (status ${result.status}).`);
      }
    },
    onError: () => {
      setActionError("The action could not reach the companion server. Nothing was recorded.");
    },
  });
  const runAction = (body: Record<string, unknown>) => actionMutation.mutate(body);
  const busy = actionMutation.isPending;

  return {
    actionError,
    actionNotice,
    statusChoice,
    setStatusChoice,
    ruling,
    setRuling,
    gate,
    setGate,
    acceptDrift,
    setAcceptDrift,
    supersedeTarget,
    setSupersedeTarget,
    runAction,
    busy,
    invalidate,
  };
}

export type DispositionState = ReturnType<typeof useDisposition>;
