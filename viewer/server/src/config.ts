// The artifact-side settings seam for the companion server's
// address — the mirror of server/config.py (Python), which is
// the server's own seam. Precedence: WB_VIEWER_* env (the same
// names the Python seam reads) > the defaults below. The
// defaults live ONLY here: no other module in viewer/ names
// the server's host or port, and the client never sees the
// address at all — actions resolve it server-side and hand it
// to the privileged bridge as validated args (the git repo
// viewer's pattern).

export interface CompanionAddress {
  host: string;
  port: number;
}

// Loopback default: the companion server binds loopback only
// (SPEC §7). 8792 is this harness's port; 8791 is the git
// repo viewer's.
const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 8792;

export function companionAddress(
  env: Record<string, string | undefined> = Bun.env,
): CompanionAddress {
  const rawPort = env.WB_VIEWER_PORT;
  const parsed = rawPort ? Number.parseInt(rawPort, 10) : Number.NaN;
  const port = Number.isInteger(parsed) && parsed >= 1 && parsed <= 65535 ? parsed : DEFAULT_PORT;
  const host = env.WB_VIEWER_HOST?.trim();
  return { host: host ? host : DEFAULT_HOST, port };
}

export function unreachableMessage(address: CompanionAddress): string {
  return (
    `Companion server unreachable on ${address.host}:${address.port} — ` +
    "is the workbench-viewer server running?"
  );
}
