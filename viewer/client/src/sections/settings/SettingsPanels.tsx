// Settings → Workspace + Messages panels (repo-home
// spec §3). Workspace is the server's EFFECTIVE
// configuration, READ-ONLY — server config is edited in
// its config file through the seam, never from this UI
// in v1; the panel exists so "what is this instance
// actually running" is answerable in one place. Messages
// shows the §5.3 policy in force, the store counts, the
// last cleanup record, and the guarded manual controls
// (§5.4): Run cleanup, purge-archived, purge-drafts —
// each behind the two-step confirm pattern, each landing
// as a message_event through lib/.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/Button";
import { api, type EffectiveSettingsPayload } from "../../lib/api";
import { formatCount, formatDateTime } from "../../lib/format";
import { messageStateLabel } from "../../lib/labels";
import { ErrorWell, SkeletonWell } from "../shared";

const panelTitleStyle: React.CSSProperties = {
  fontSize: "var(--wb-font-size-xs)",
  lineHeight: "var(--wb-line-height-xs)",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--wb-content-secondary)",
  marginTop: "var(--wb-space-32)",
};

const rowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: "var(--wb-space-24)",
  padding: "var(--wb-space-8) 0",
  borderBottom: "1px solid var(--wb-border-default)",
};

const labelStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  whiteSpace: "nowrap",
};

const valueStyle: React.CSSProperties = {
  color: "var(--wb-content-secondary)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  textAlign: "right",
  overflowWrap: "anywhere",
};

function fmtValue(value: unknown): string {
  if (value == null) return "—";
  if (Array.isArray(value)) return value.map(fmtValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Row({ label, value, mono }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <div style={rowStyle}>
      <div style={labelStyle}>{label}</div>
      <div style={valueStyle} className={mono ? "mono" : undefined}>
        {fmtValue(value)}
      </div>
    </div>
  );
}

type CleanupAction = "run" | "archived" | "drafts";

const ACTION_LABELS: Record<CleanupAction, string> = {
  run: "Run cleanup now",
  archived: "Purge archived",
  drafts: "Purge drafts",
};

function MessagesPanel({ settings }: { settings: EffectiveSettingsPayload }) {
  const queryClient = useQueryClient();
  const [armed, setArmed] = useState<CleanupAction | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const messages = settings.messages;

  const mutation = useMutation({
    mutationFn: (action: CleanupAction) =>
      api.cleanupMessages({
        body: action === "run" ? { confirm: true } : { confirm: true, purge: action },
      }),
    onSuccess: (reply, action) => {
      setArmed(null);
      if (reply.payload == null) {
        setResult(reply.error ?? "the cleanup call was refused.");
        return;
      }
      const payload = reply.payload as {
        purged?: number;
        cleanup?: Record<string, number>;
      };
      setResult(
        action === "run"
          ? `Cleanup ran: ${Object.entries(payload.cleanup ?? {})
              .map(([k, n]) => `${k} ${n}`)
              .join(" · ")}`
          : `Purged ${payload.purged ?? 0} messages.`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["settings-effective"],
      });
      void queryClient.invalidateQueries({ queryKey: ["messages"] });
    },
    onError: () => setResult("the cleanup call failed."),
  });

  if (messages.error) {
    return (
      <>
        <h2 style={panelTitleStyle}>Messages</h2>
        <ErrorWell section="Messages" message={messages.error} />
      </>
    );
  }
  const counts = messages.counts ?? {};
  const policy = messages.policy ?? {};
  const policyRows: [string, string][] = [
    ["Drafts untouched → purged", "draft_ttl_days"],
    ["Done → archived", "done_archive_days"],
    ["Archived → purged", "archive_ttl_days"],
    ["Awaiting-pickup badge", "awaiting_badge_days"],
    ["Per-project cap", "per_project_cap"],
  ];
  return (
    <>
      <h2 style={panelTitleStyle}>Messages</h2>
      <Row label="Store" value={messages.db} mono />
      {(["draft", "sent", "acknowledged", "done", "archived"] as const).map((state) => (
        <Row key={state} label={messageStateLabel(state)} value={formatCount(counts[state] ?? 0)} />
      ))}
      <Row label="Watcher outbox rows" value={formatCount(messages.outbox_rows ?? 0)} />
      <Row label="Notify checkpoint" value={formatCount(messages.notify_checkpoint ?? 0)} />
      <Row
        label="Last cleanup"
        value={
          messages.last_cleanup_at
            ? `${formatDateTime(messages.last_cleanup_at)}${
                messages.last_cleanup_counts
                  ? ` — ${Object.entries(messages.last_cleanup_counts)
                      .map(([k, n]) => `${k} ${n}`)
                      .join(" · ")}`
                  : ""
              }`
            : "has not run yet"
        }
      />
      {policyRows.map(([label, key]) => (
        <Row
          key={key}
          label={label}
          value={
            key === "per_project_cap"
              ? `${formatCount(policy[key])} messages`
              : `${formatCount(policy[key])} days`
          }
        />
      ))}
      <div
        style={{
          display: "flex",
          gap: "var(--wb-space-8)",
          alignItems: "center",
          flexWrap: "wrap",
          paddingTop: "var(--wb-space-16)",
        }}
      >
        {(Object.keys(ACTION_LABELS) as CleanupAction[]).map((action) =>
          armed === action ? (
            <span
              key={action}
              style={{ display: "inline-flex", gap: "var(--wb-space-8)", alignItems: "center" }}
            >
              <Button
                variant="danger"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate(action)}
              >
                Confirm: {ACTION_LABELS[action].toLowerCase()}
              </Button>
              <Button variant="ghost" onClick={() => setArmed(null)}>
                Cancel
              </Button>
            </span>
          ) : (
            <Button
              key={action}
              variant={action === "run" ? "secondary" : "ghost"}
              disabled={mutation.isPending || armed != null}
              onClick={() => {
                setResult(null);
                setArmed(action);
              }}
            >
              {ACTION_LABELS[action]}
            </Button>
          ),
        )}
      </div>
      {result ? (
        <p role="status" style={{ color: "var(--wb-content-secondary)" }}>
          {result}
        </p>
      ) : null}
    </>
  );
}

export function SettingsPanels() {
  const query = useQuery({
    queryKey: ["settings-effective"],
    queryFn: () => api.getEffectiveSettings({}),
  });
  if (query.isPending) return <SkeletonWell label="the effective settings" />;
  if (query.isError || !query.data.payload) {
    return (
      <ErrorWell
        section="Settings"
        message={query.data?.error ?? "the companion server did not answer."}
      />
    );
  }
  const settings = query.data.payload as unknown as EffectiveSettingsPayload;
  const config = settings.config;
  const host = config.host;
  const port = config.port;
  return (
    <>
      <h2 style={panelTitleStyle}>Workspace</h2>
      <Row
        label="Server"
        value={host != null && port != null ? `${fmtValue(host)}:${fmtValue(port)}` : null}
        mono
      />
      <Row label="Workspace root" value={config.workspace_root} mono />
      <Row label="Sweep roots" value={config.sweep_roots} mono />
      <Row label="State directory" value={config.state_dir} mono />
      <Row label="Config file" value={settings.config_file} mono />
      <Row label="Config hash" value={settings.config_hash} mono />
      <Row label="File editing" value={config.file_editing_enabled === true ? "on" : "off"} />
      <MessagesPanel settings={settings} />
    </>
  );
}
