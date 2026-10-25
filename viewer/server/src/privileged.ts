// Privileged host handlers — raw node:net socket to the
// companion server. The hosting daemon's egress proxy breaks
// loopback fetch (the git repo viewer's documented trap, SPEC
// §8), so every feed travels this socket path, never fetch.
// Host/port/method/path/body are validated args supplied by
// the actions from the config seam (server/src/config.ts);
// this module hardcodes no target.
import { connect } from "node:net";
import { definePrivilegedContracts, definePrivilegedHandlers, z } from "@hatch/space-sdk";

const TIMEOUT_MS = 12000;

interface SocketResult {
  status: number;
  json: unknown;
}

function fetchJson(args: {
  host: string;
  port: number;
  method: string;
  path: string;
  body?: string | null;
}): Promise<SocketResult> {
  return new Promise((resolve) => {
    let settled = false;
    const done = (value: SocketResult) => {
      if (!settled) {
        settled = true;
        resolve(value);
      }
    };
    const socket = connect(args.port, args.host);
    socket.setTimeout(TIMEOUT_MS);
    const chunks: Buffer[] = [];
    socket.on("connect", () => {
      const body = args.body ?? "";
      let request =
        `${args.method} ${args.path} HTTP/1.1\r\n` +
        `Host: ${args.host}:${args.port}\r\n` +
        "Accept: application/json\r\nConnection: close\r\n";
      if (args.method === "POST") {
        request +=
          `Content-Type: application/json\r\n` + `Content-Length: ${Buffer.byteLength(body)}\r\n`;
      }
      request += "\r\n";
      if (args.method === "POST") request += body;
      socket.write(request);
    });
    socket.on("data", (chunk: Buffer) => chunks.push(chunk));
    socket.on("timeout", () => {
      socket.destroy();
      done({ status: 0, json: { error: `timed out after ${TIMEOUT_MS}ms` } });
    });
    socket.on("error", (err) => {
      done({ status: 0, json: { error: err.message } });
    });
    socket.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      const splitAt = raw.indexOf("\r\n\r\n");
      if (splitAt === -1) {
        done({ status: 0, json: { error: "malformed HTTP response" } });
        return;
      }
      const head = raw.slice(0, splitAt);
      const match = /^HTTP\/1\.[01] (\d{3})/.exec(head);
      const status = match ? Number(match[1]) : 0;
      let body = raw.slice(splitAt + 4);
      if (/transfer-encoding:\s*chunked/i.test(head)) body = dechunk(body);
      let json: unknown = null;
      try {
        json = JSON.parse(body) as unknown;
      } catch {
        json = null;
      }
      done({ status, json });
    });
  });
}

function dechunk(body: string): string {
  let out = "";
  let rest = body;
  for (;;) {
    const end = rest.indexOf("\r\n");
    if (end === -1) return out;
    const size = Number.parseInt(rest.slice(0, end), 16);
    if (!Number.isFinite(size) || size <= 0) return out;
    out += rest.slice(end + 2, end + 2 + size);
    rest = rest.slice(end + 2 + size + 2);
  }
}

export const privileged = definePrivilegedContracts({
  wbApi: {
    request: z.object({
      host: z.string().min(1),
      port: z.number().int().min(1).max(65535),
      method: z.enum(["GET", "POST"]).default("GET"),
      path: z.string(),
      body: z.string().nullable().optional(),
    }),
    response: z.object({ status: z.number(), json: z.unknown() }),
    capabilities: ["network.loopback"],
    timeoutMs: 20000,
  },
});

export const privilegedHandlers = definePrivilegedHandlers(privileged, {
  async wbApi(args) {
    return fetchJson({
      host: args.host,
      port: args.port,
      method: args.method ?? "GET",
      path: args.path,
      body: args.body ?? null,
    });
  },
});
