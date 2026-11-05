// RefreshButton — the shell's manual refresh
// (cache-refresh plan, design point 5): one tap busts
// the companion server's sweep + feed caches through
// the forceRefresh action, then invalidates every
// react-query query so all sections re-read fresh —
// the escape hatch for when the owner knows something
// changed and will not wait out a TTL or a poll.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "../components/Button";
import { api } from "../lib/api";

export function RefreshButton({ style }: { style?: React.CSSProperties }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.forceRefresh({}),
    onSettled: () => {
      // Even an unreachable server still gets the client
      // half of the hatch: every query re-reads.
      void queryClient.invalidateQueries();
    },
  });
  return (
    <span style={style}>
      <Button
        variant="ghost"
        ariaLabel="Refresh all data"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? "Refreshing…" : "Refresh"}
      </Button>
    </span>
  );
}
