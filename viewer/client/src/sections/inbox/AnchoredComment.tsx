// Anchored comment box (repo-home spec D7): the second
// and only other compose surface — the SAME composer as
// the Inbox's, with the anchor preset by the surface the
// comment is attached to (a plan in the Overview showcase,
// a todo, an entry). Collapsed to one kit button until
// opened; the anchor is shown, never editable, so a
// comment can never drift off the thing it is about.

import { useState } from "react";
import { Button } from "../../components/Button";
import { MessageComposer } from "./MessageComposer";

export function AnchoredComment({
  slug,
  projectName,
  anchorType,
  anchorRef,
}: {
  slug: string;
  projectName: string;
  anchorType: "plan" | "todo" | "entry" | "repo";
  anchorRef: string;
}) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <Button variant="ghost" onClick={() => setOpen(true)}>
        Comment
      </Button>
    );
  }
  return (
    <div
      style={{
        border: "1px solid var(--wb-border-default)",
        borderRadius: "var(--wb-radius-md)",
        padding: "var(--wb-space-12)",
        marginTop: "var(--wb-space-8)",
      }}
    >
      <MessageComposer
        projects={[{ slug, name: projectName }]}
        fixedProject={slug}
        presetAnchor={{ type: anchorType, ref: anchorRef }}
        onPosted={() => setOpen(false)}
      />
    </div>
  );
}
