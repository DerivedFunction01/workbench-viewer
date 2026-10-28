// Settings → Repos tracking panel (absorption plan,
// step 9): the repo registry's editing surface. The
// registry is the harness-owned tracking metadata for
// browsed repos (lib/repo_state.py) — display name,
// expected publication, pinned, ignored, notes. Edits
// post a patch of the changed fields only, through the
// one mutation path; publication and exposure themselves
// are derived from the repos and are never edited here.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../components/Button";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Toggle } from "../../components/Toggle";
import { api, type RepoRegistryEntry, type ReposRegistryPayload } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { expectedLabel } from "../../lib/labels";
import { reposHref } from "../../lib/routing";
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

const labelStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  whiteSpace: "nowrap",
};

const inputStyle: React.CSSProperties = {
  background: "var(--wb-surface-2)",
  border: "1px solid var(--wb-border-default)",
  borderRadius: "var(--wb-radius-sm)",
  color: "var(--wb-content-primary)",
  fontSize: "var(--wb-font-size-sm)",
  lineHeight: "var(--wb-line-height-sm)",
  padding: "var(--wb-space-8)",
  minHeight: "38px",
  width: "100%",
  minWidth: 0,
};

const fieldRowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "140px 1fr",
  gap: "var(--wb-space-8) var(--wb-space-16)",
  alignItems: "center",
  padding: "var(--wb-space-8) 0",
};

type Expected = RepoRegistryEntry["expected"];

const EXPECTED_OPTIONS: { value: Expected; label: string }[] = [
  { value: "published", label: expectedLabel("published") },
  { value: "local_ok", label: expectedLabel("local_ok") },
  { value: "untracked", label: expectedLabel("untracked") },
];

function RegistryRow({ id, entry }: { id: string; entry: RepoRegistryEntry }) {
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState(entry.display_name);
  const [expected, setExpected] = useState<Expected>(entry.expected);
  const [pinned, setPinned] = useState(entry.pinned);
  const [ignored, setIgnored] = useState(entry.ignored);
  const [notes, setNotes] = useState(entry.notes);
  const [result, setResult] = useState<string | null>(null);

  const patch: Record<string, unknown> = {};
  if (displayName !== entry.display_name) patch.display_name = displayName;
  if (expected !== entry.expected) patch.expected = expected;
  if (pinned !== entry.pinned) patch.pinned = pinned;
  if (ignored !== entry.ignored) patch.ignored = ignored;
  if (notes !== entry.notes) patch.notes = notes;
  const dirty = Object.keys(patch).length > 0;

  const mutation = useMutation({
    mutationFn: () => api.updateReposRegistry({ id, patch }),
    onSuccess: (reply) => {
      const updated = (reply.payload as { registry?: RepoRegistryEntry } | null)?.registry;
      if (!updated) {
        setResult(reply.error ?? "the update was refused — nothing was written.");
        return;
      }
      // Reseed from the server's own returned entry (the
      // row is keyed by id only, so a registry refetch
      // never wipes another row's unsaved edits).
      setDisplayName(updated.display_name);
      setExpected(updated.expected);
      setPinned(updated.pinned);
      setIgnored(updated.ignored);
      setNotes(updated.notes);
      setResult("Saved.");
      void queryClient.invalidateQueries({ queryKey: ["repos-registry"] });
      void queryClient.invalidateQueries({ queryKey: ["repos"] });
    },
    onError: () => setResult("The update call failed — nothing was written."),
  });

  return (
    <div
      style={{
        border: "1px solid var(--wb-border-default)",
        borderRadius: "var(--wb-radius-md)",
        background: "var(--wb-surface-2)",
        padding: "var(--wb-space-16)",
        marginBottom: "var(--wb-space-12)",
      }}
    >
      <div
        style={{
          display: "flex",
          gap: "var(--wb-space-12)",
          alignItems: "baseline",
          flexWrap: "wrap",
          marginBottom: "var(--wb-space-8)",
        }}
      >
        <a
          href={reposHref(id)}
          className="mono"
          style={{
            color: "var(--wb-accent)",
            textDecoration: "none",
            fontWeight: 600,
            overflowWrap: "anywhere",
          }}
        >
          {id}
        </a>
        <span
          className="mono"
          style={{
            color: "var(--wb-content-muted)",
            fontSize: "var(--wb-font-size-xs)",
            overflowWrap: "anywhere",
          }}
        >
          {entry.root}
        </span>
        <span
          style={{
            color: "var(--wb-content-muted)",
            fontSize: "var(--wb-font-size-xs)",
            marginLeft: "auto",
          }}
        >
          first seen {formatDateTime(entry.first_seen)} · last seen{" "}
          {formatDateTime(entry.last_seen)}
        </span>
      </div>
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Display name</span>
        <input
          style={inputStyle}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          aria-label={`Display name for ${id}`}
        />
      </div>
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Expected</span>
        <SegmentedControl
          ariaLabel={`Expected publication for ${id}`}
          options={EXPECTED_OPTIONS}
          value={expected}
          onChange={(next) => setExpected(next as Expected)}
        />
      </div>
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Pinned</span>
        <Toggle checked={pinned} onChange={setPinned} label="Pinned" />
      </div>
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Ignored</span>
        <Toggle checked={ignored} onChange={setIgnored} label="Ignored" />
      </div>
      <div style={fieldRowStyle}>
        <span style={labelStyle}>Notes</span>
        <input
          style={inputStyle}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          aria-label={`Notes for ${id}`}
        />
      </div>
      <div
        style={{
          display: "flex",
          gap: "var(--wb-space-8)",
          alignItems: "center",
          paddingTop: "var(--wb-space-8)",
        }}
      >
        <Button disabled={!dirty || mutation.isPending} onClick={() => mutation.mutate()}>
          Save tracking
        </Button>
        {dirty ? (
          <span
            style={{ color: "var(--wb-content-secondary)", fontSize: "var(--wb-font-size-sm)" }}
          >
            Unsaved changes
          </span>
        ) : null}
        {result ? (
          <span role="status" style={{ color: "var(--wb-content-secondary)" }}>
            {result}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function ReposTrackingPanel() {
  const query = useQuery({
    queryKey: ["repos-registry"],
    queryFn: () => api.getReposRegistry({}),
  });
  const payload = query.data?.payload as unknown as ReposRegistryPayload | null;
  const ids = payload ? Object.keys(payload.repos).sort() : [];
  return (
    <>
      <h2 style={panelTitleStyle}>Repos — tracking</h2>
      <p
        style={{
          color: "var(--wb-content-secondary)",
          fontSize: "var(--wb-font-size-sm)",
          margin: "var(--wb-space-8) 0 var(--wb-space-16)",
        }}
      >
        What the harness expects of each browsed repo. The census reconciles this registry on every
        serve — new repos arrive as Untracked; an entry whose directory vanishes is kept and shown
        as missing in Repos until it is pruned on a healthy scan.
      </p>
      {query.isPending ? (
        <SkeletonWell label="the repo registry" />
      ) : query.isError || !payload ? (
        <ErrorWell
          section="Repos tracking"
          message={query.data?.error ?? "the repo registry did not answer."}
        />
      ) : ids.length === 0 ? (
        <p style={{ color: "var(--wb-content-muted)" }}>No repos in the registry yet.</p>
      ) : (
        ids.map((id) => {
          const entry = payload.repos[id];
          if (!entry) return null;
          return <RegistryRow key={id} id={id} entry={entry} />;
        })
      )}
    </>
  );
}
