"""Atomic review-state writes and a hash-chained append-only event ledger."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document, validate_jsonl_file


class StateStoreError(ValueError):
    """Raised when a state mutation would violate integrity constraints."""


class LedgerError(StateStoreError):
    """Raised when an event would violate ledger integrity."""


@contextmanager
def _exclusive_file_lock(path: Path, timeout_seconds: float = 30.0):
    """Serialize ledger mutations across processes on Windows and POSIX."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise LedgerError(f"timed out waiting for event ledger lock: {path}") from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def atomic_write_json(path: Path, document: Any, schema_name: str | None = None) -> None:
    if schema_name:
        validate_document(document, schema_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def append_jsonl_record(
    path: Path,
    document: dict[str, Any],
    schema_name: str,
    *,
    unique_fields: tuple[str, ...] = (),
    timeout_seconds: float = 30.0,
) -> None:
    """Validate and durably append one record while serializing all writers."""
    lock_path = path.with_name(path.name + ".lock")
    with _exclusive_file_lock(lock_path, timeout_seconds=timeout_seconds):
        try:
            existing_records = validate_jsonl_file(path, schema_name)
            validate_document(document, schema_name)
        except SchemaValidationError as exc:
            raise StateStoreError(str(exc)) from exc
        for field in unique_fields:
            if field not in document:
                raise StateStoreError(f"unique field is missing from record: {field}")
            value = document[field]
            if any(existing.get(field) == value for existing in existing_records):
                raise StateStoreError(f"{field} already exists in {path}: {value}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(document).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def _event_hash(event: dict[str, Any]) -> str:
    unhashed = {key: value for key, value in event.items() if key != "event_hash"}
    return sha256_json(unhashed)


@dataclass(frozen=True)
class AppendResult:
    appended: bool
    event: dict[str, Any]


class EventLedger:
    def __init__(self, path: Path):
        self.path = path

    def read(self) -> list[dict[str, Any]]:
        try:
            return validate_jsonl_file(self.path, "event_ledger")
        except SchemaValidationError as exc:
            raise LedgerError(str(exc)) from exc

    def append(self, event: dict[str, Any]) -> AppendResult:
        lock_path = self.path.with_name(self.path.name + ".lock")
        with _exclusive_file_lock(lock_path):
            return self._append_locked(event)

    def _append_locked(self, event: dict[str, Any]) -> AppendResult:
        events = self.read()
        event_id = event.get("event_id")
        idempotency_key = event.get("idempotency_key")
        for existing in events:
            if existing["event_id"] == event_id and existing["idempotency_key"] != idempotency_key:
                raise LedgerError(f"event_id already exists with another idempotency key: {event_id}")
            if existing["idempotency_key"] == idempotency_key:
                return AppendResult(appended=False, event=existing)

        candidate = dict(event)
        candidate["previous_event_hash"] = events[-1]["event_hash"] if events else None
        candidate["event_hash"] = _event_hash(candidate)
        execution = candidate.get("execution", {})
        if execution.get("retry_count", 0) > execution.get("retry_budget", 0):
            raise LedgerError("retry_count exceeds retry_budget")
        try:
            validate_document(candidate, "event_ledger")
        except SchemaValidationError as exc:
            raise LedgerError(str(exc)) from exc

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(candidate).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return AppendResult(appended=True, event=candidate)

    def verify(self) -> list[str]:
        try:
            events = self.read()
        except LedgerError as exc:
            return [str(exc)]
        issues: list[str] = []
        event_ids: set[str] = set()
        idempotency_keys: set[str] = set()
        previous_hash: str | None = None
        for index, event in enumerate(events, start=1):
            if event["event_id"] in event_ids:
                issues.append(f"event {index}: duplicate event_id {event['event_id']}")
            if event["idempotency_key"] in idempotency_keys:
                issues.append(f"event {index}: duplicate idempotency_key {event['idempotency_key']}")
            if event["previous_event_hash"] != previous_hash:
                issues.append(f"event {index}: previous_event_hash does not match chain")
            if event["event_hash"] != _event_hash(event):
                issues.append(f"event {index}: event_hash mismatch")
            execution = event["execution"]
            if execution["retry_count"] > execution["retry_budget"]:
                issues.append(f"event {index}: retry_count exceeds retry_budget")
            event_ids.add(event["event_id"])
            idempotency_keys.add(event["idempotency_key"])
            previous_hash = event["event_hash"]
        return issues
