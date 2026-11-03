"""Generic notify targets for the watcher core
(repo-home spec §15.1).

The outbox table is the interface; notify targets are an
OPTIONAL convenience the server's maintenance loop fires
for new outbox rows: a webhook URL (POST the event JSON)
and/or a local command (the event JSON on its stdin).
Nothing here knows what consumes the events — Muse is
one consumer among any (§15.2); this module is the
system-agnostic half.

Firing is best-effort and per-target: a dead webhook never
blocks the command target, and a failure is reported in
the result dict, never raised into the server loop. The
loop advances its checkpoint past events it ATTEMPTED —
delivery is at-most-once per target by design (the durable
queue is the outbox + the messages themselves, §13;
notify is a wake-up, not the record).
"""

import json
import subprocess
import urllib.request


def event_payload(event: dict) -> dict:
    """The JSON a target receives: the outbox row verbatim
    (id, message id, project, anchor, summary, at)."""
    return {
        "id": event["id"],
        "message_id": event["message_id"],
        "project_slug": event["project_slug"],
        "anchor_type": event["anchor_type"],
        "anchor_ref": event["anchor_ref"],
        "anchor_summary": event["anchor_summary"],
        "event": event["event"],
        "at": event["at"],
    }


def _fire_webhook(url: str, payload: dict,
                  timeout: float) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=raw, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) \
                as resp:
            return {"target": "webhook", "ok": True,
                    "detail": f"HTTP {resp.status}"}
    except Exception as e:  # a dead target is data, not a crash
        return {"target": "webhook", "ok": False,
                "detail": str(e)[:200]}


def _fire_command(command, payload: dict,
                  timeout: float) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    try:
        if isinstance(command, str):
            proc = subprocess.run(
                command, shell=True, input=raw,
                capture_output=True, timeout=timeout)
        else:
            proc = subprocess.run(
                [str(c) for c in command], input=raw,
                capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"target": "command", "ok": False,
                "detail": str(e)[:200]}
    if proc.returncode != 0:
        return {"target": "command", "ok": False,
                "detail": f"exit {proc.returncode}: "
                          f"{proc.stderr.decode('utf-8', 'replace')[:160]}"}
    return {"target": "command", "ok": True,
            "detail": "exit 0"}


def fire_targets(targets: dict, events: list,
                 *, timeout: float = 10.0) -> list:
    """Fire every configured target once per event.
    `targets` = {"webhook": url|None, "command": str|list|
    None} (built by the server from the config seam).
    Returns one result dict per (event, target) attempt:
    {event_id, target, ok, detail}. No targets configured
    -> no attempts (the outbox alone is the interface)."""
    results = []
    webhook = targets.get("webhook")
    command = targets.get("command")
    if not webhook and not command:
        return results
    for event in events:
        payload = event_payload(event)
        if webhook:
            results.append({
                "event_id": event["id"],
                **_fire_webhook(webhook, payload, timeout)})
        if command:
            results.append({
                "event_id": event["id"],
                **_fire_command(command, payload, timeout)})
    return results
