"""B2 Event Notification receiver — the event-driven stage machine (P3).

CastIron's invariant I1: a run reaches PUBLISHED *only* via B2 object-created
events, not by polling. B2 fires a notification as each artifact lands in
``runs/{date}/{run}/assets/{stage}.*``; this module verifies the delivery
(HMAC-SHA256), maps the object back to its run+stage, and advances the
downstream stage machine (render → mix → verify → publish) **idempotently** —
duplicate or reordered deliveries are no-ops.

CREDENTIAL-INDEPENDENT: the parsing, HMAC, key-mapping, and idempotent
transition logic are exercised OFFLINE with synthetic B2 payloads (see
tests/test_webhooks.py). The only LIVE-gated piece is the real bucket rule
firing real deliveries — verified at P3 with credentials.

✔ SDKCHK #7 (RESOLVED, 2026-07-26): confirmed against Backblaze's Event
Notifications reference guide — the delivered header is
``X-Bz-Event-Notification-Signature`` (HTTP header names are case-insensitive,
so our lowercase default matches) and its value is ``v1=<lowercase hex HMAC-
SHA256 over the raw body>``. ``verify_signature`` splits on ``=`` so it accepts
the real ``v1=`` prefix (and bare hex); ``sign`` mirrors B2's ``v1=`` exactly.
A full live round-trip additionally needs the public receiver (post-deploy).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from castiron.db import Database

# Confirmed against B2 docs (SDKCHK #7). Case-insensitive per HTTP; the ASGI
# layer lowercases header keys, so this lowercase form matches B2's mixed case.
SIGNATURE_HEADER = "x-bz-event-notification-signature"
# Required artifacts (from the parallel fan-out) before MIX may start.
REQUIRED_ARTIFACT_STAGES = ("narration", "music", "cover")
# Downstream event-driven progression after all artifacts land.
DOWNSTREAM_ORDER = ("mix", "verify", "publish")


# --------------------------------------------------------------------------- #
# Signature verification
# --------------------------------------------------------------------------- #
def verify_signature(body: bytes, header_sig: str | None, secret: str | None) -> bool:
    """Constant-time HMAC-SHA256 check of the raw request body.

    If no secret is configured (OFFLINE / local dev), verification is skipped
    and returns True — the receiver is still exercised, just unauthenticated.
    A configured secret with a missing/blank header fails closed.
    """
    if not secret:
        return True
    if not header_sig:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    # B2 sends "v1=<hex>"; also accept bare hex. Split on "=" → take the hex.
    got = header_sig.split("=", 1)[-1].strip()
    return hmac.compare_digest(expected, got)


def sign(body: bytes, secret: str) -> str:
    """Produce the header value a correctly-configured B2 rule would send.

    Mirrors B2's ``v1=<lowercase hex HMAC-SHA256>`` (SDKCHK #7). Used by tests to
    forge realistic deliveries; the counterpart of ``verify_signature``.
    """
    return "v1=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- #
# Payload parsing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class B2Event:
    event_id: str
    event_type: str
    bucket: str
    object_name: str
    object_size: int
    version_id: str

    @property
    def is_object_created(self) -> bool:
        return self.event_type.startswith("b2:ObjectCreated")


def parse_events(body: bytes) -> list[B2Event]:
    """Parse a B2 Event Notification payload into typed events.

    Tolerant of the documented ``{"events": [...]}`` envelope; malformed JSON
    raises ValueError (the route turns that into a 400).
    """
    try:
        doc = json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - trivial
        raise ValueError(f"invalid JSON body: {exc}") from exc
    out: list[B2Event] = []
    for ev in doc.get("events", []):
        out.append(
            B2Event(
                event_id=str(ev.get("eventId", "")),
                event_type=str(ev.get("eventType", "")),
                bucket=str(ev.get("bucketName", "")),
                object_name=str(ev.get("objectName", "")),
                object_size=int(ev.get("objectSize", 0) or 0),
                version_id=str(ev.get("objectVersionId", "")),
            )
        )
    return out


def run_stage_from_key(object_name: str) -> tuple[str, str] | None:
    """Map ``runs/{date}/{run}/assets/{stage}.*`` → (run_id, stage).

    Returns None for keys outside the run-artifact namespace (ignored).
    """
    parts = object_name.strip("/").split("/")
    # runs / {date} / {run} / assets / {file}
    if len(parts) >= 5 and parts[0] == "runs" and parts[3] == "assets":
        run_id = parts[2]
        stem = parts[4].split(".", 1)[0]
        # narration/music/cover artifacts, or the mix output
        for stage in (*REQUIRED_ARTIFACT_STAGES, "mix"):
            if stem.startswith(stage):
                return run_id, stage
    return None


# --------------------------------------------------------------------------- #
# Idempotent stage machine
# --------------------------------------------------------------------------- #
@dataclass
class Transition:
    run_id: str
    advanced_to: str | None      # stage newly entered, or None for no-op/duplicate
    duplicate: bool = False
    reason: str = ""


class StageMachine:
    """Advances a run's downstream stages on B2 object-created events.

    Idempotency is DB-backed: every processed ``eventId`` is recorded as an
    event row (type ``b2.processed``); a replayed delivery is a no-op. State is
    derived from which artifacts have landed, so reordered deliveries converge
    to the same result.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def _already_processed(self, run_id: str, event_id: str) -> bool:
        for row in self.db.list_events(run_id):
            if row.type == "b2.processed":
                if json.loads(row.payload_json).get("event_id") == event_id:
                    return True
        return False

    def _artifacts_present(self, run_id: str) -> set[str]:
        seen: set[str] = set()
        for row in self.db.list_events(run_id):
            if row.type == "b2.object":
                if st := json.loads(row.payload_json).get("stage"):
                    seen.add(st)
        return seen

    def handle(self, event: B2Event) -> Transition:
        if not event.is_object_created:
            return Transition("", None, reason="ignored: not ObjectCreated")
        mapped = run_stage_from_key(event.object_name)
        if mapped is None:
            return Transition("", None, reason="ignored: key outside run namespace")
        run_id, stage = mapped

        # Defensive: a delivery for a run we don't own (foreign bucket, replay
        # after cleanup) is ignored, never a 500.
        if self.db.get_run(run_id) is None:
            return Transition(run_id, None, reason="ignored: unknown run")

        if self._already_processed(run_id, event.event_id):
            return Transition(run_id, None, duplicate=True, reason="duplicate delivery")

        # record the raw object arrival + mark the event processed (idempotency)
        self.db.insert_event(
            run_id, "b2", "b2.object",
            json.dumps({"stage": stage, "key": event.object_name}),
        )
        self.db.insert_event(
            run_id, "b2", "b2.processed",
            json.dumps({"event_id": event.event_id}),
        )

        present = self._artifacts_present(run_id)

        # An artifact landing: advance to MIX once all three are present.
        if stage in REQUIRED_ARTIFACT_STAGES:
            if REQUIRED_ARTIFACT_STAGES and set(REQUIRED_ARTIFACT_STAGES) <= present:
                return self._enter(run_id, "mix")
            return Transition(run_id, None, reason=f"artifact {stage}; awaiting others")

        # The mix output landing → verify → publish is the caller's job, but the
        # machine records mix arrival and signals the verify stage.
        if stage == "mix":
            return self._enter(run_id, "verify")

        return Transition(run_id, None, reason="no transition")  # pragma: no cover - defensive; run_stage_from_key only yields artifact/mix stages

    def _enter(self, run_id: str, stage: str) -> Transition:
        # idempotent: don't re-enter a stage already recorded
        existing = {s.name for s in self.db.list_stages(run_id)}
        if stage in existing and any(
            s.name == stage and s.state in {"running", "done"}
            for s in self.db.list_stages(run_id)
        ):
            return Transition(run_id, None, reason=f"{stage} already entered")
        self.db.upsert_stage(run_id, stage, state="running")
        self.db.insert_event(
            run_id, "b2", "stage.enter",
            json.dumps({"stage": stage, "via": "b2-event"}),
        )
        return Transition(run_id, stage, reason=f"entered {stage} via B2 event")


def handle_delivery(
    db: Database, body: bytes, header_sig: str | None, secret: str | None
) -> dict[str, Any]:
    """Verify + process a full delivery. Raises PermissionError on bad signature."""
    if not verify_signature(body, header_sig, secret):
        raise PermissionError("bad HMAC signature")
    machine = StageMachine(db)
    transitions = [machine.handle(ev) for ev in parse_events(body)]
    return {
        "processed": len(transitions),
        "advanced": [t.advanced_to for t in transitions if t.advanced_to],
        "duplicates": sum(1 for t in transitions if t.duplicate),
    }
