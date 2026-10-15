"""Append-only audit trail in output/audit_trail.json.

The file is one JSON array. Every event is appended: the existing events are
read, the new one added at the end, and the file replaced atomically under a
lock, so a crash mid-write can't truncate the history and two runs can't
overwrite each other. Nothing ever removes or rewrites an earlier event.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from models import AuditEvent


def ensure_audit_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def _append(path: Path, event: dict) -> None:
    ensure_audit_file(path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            text = path.read_text(encoding="utf-8").strip() or "[]"
            events = json.loads(text)
            if not isinstance(events, list):
                raise ValueError(f"{path} must hold a JSON array; refusing to overwrite it.")
            events.append(event)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".audit_", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, default=str)
                f.write("\n")
            os.replace(tmp, path)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class AuditTrail:
    """Records the events of one desk run, numbered in order.

    `listeners` are called with each event (as a dict) right after it's written,
    which is how the API streams a run live to the dashboard.
    """

    def __init__(self, path: Path, run_id: str | None = None, listeners: list[Callable[[dict], None]] | None = None):
        self.path = path
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.seq = 0
        self.listeners = list(listeners or [])
        ensure_audit_file(path)

    def log(
        self,
        kind: str,
        *,
        agent: str | None,
        chain: list[str] | tuple[str, ...] = (),
        ticket_id: int | None = None,
        **details: Any,
    ) -> AuditEvent:
        self.seq += 1
        event = AuditEvent(
            event_id=uuid.uuid4().hex,
            run_id=self.run_id,
            seq=self.seq,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            agent=agent,
            kind=kind,
            ticket_id=ticket_id,
            delegation_chain=list(chain),
            details=details,
        )
        record = event.model_dump(mode="json")
        _append(self.path, record)
        for listener in self.listeners:
            listener(record)
        return event
