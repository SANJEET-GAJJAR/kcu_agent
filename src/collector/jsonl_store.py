"""Append-only JSONL store for candle records.

Guarantees:
  - Each line is a valid JSON object.
  - Timestamps are unique within a file.
  - Records are written in the order received.
  - Existing records survive a crash and are readable on resume.

No trading logic.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from .candle_record import CandleRecord

log = logging.getLogger(__name__)


class JsonlStoreError(Exception):
    """Raised on JSONL integrity violations."""


class JsonlStore:
    """Append-only JSONL writer with duplicate detection and resume support.

    Usage:
        store = JsonlStore(path)
        seen = store.load_seen_timestamps()   # read existing records
        store.append(record)                   # write new record
        store.flush()                          # ensure OS flush
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._seen_timestamps: set[int] = set()
        self._record_count: int = 0
        self._file = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> "JsonlStore":
        """Open the file for appending. Must be called before append()."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._load_existing()
        self._seen_timestamps = {r.timestamp for r in existing}
        self._record_count = len(self._seen_timestamps)
        self._file = self._path.open("a", encoding="utf-8")
        log.debug("Opened %s (existing records: %d)", self._path, self._record_count)
        return self

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None

    def __enter__(self) -> "JsonlStore":
        return self.open()

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, record: CandleRecord) -> bool:
        """Write record to JSONL. Returns False if already seen (duplicate skipped)."""
        if self._file is None:
            raise JsonlStoreError("Store is not open. Call open() first.")

        ts = record.timestamp
        if ts in self._seen_timestamps:
            log.debug("Skipping duplicate timestamp %d", ts)
            return False

        self._file.write(record.to_jsonl_line() + "\n")
        self._file.flush()
        self._seen_timestamps.add(ts)
        self._record_count += 1
        return True

    def flush(self) -> None:
        if self._file:
            self._file.flush()

    # ------------------------------------------------------------------
    # Read / introspect
    # ------------------------------------------------------------------

    def load_seen_timestamps(self) -> set[int]:
        """Return set of timestamps already in the file (for resume detection)."""
        return {r.timestamp for r in self._load_existing()}

    def read_all(self) -> list[CandleRecord]:
        """Read all records from the file. File must exist."""
        return list(self._load_existing())

    def _load_existing(self) -> Iterator[CandleRecord]:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    yield CandleRecord.from_dict(d)
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    raise JsonlStoreError(
                        f"{self._path}:{lineno} — invalid record: {exc}"
                    ) from exc

    @property
    def record_count(self) -> int:
        return self._record_count

    @property
    def seen_timestamps(self) -> frozenset[int]:
        return frozenset(self._seen_timestamps)

    @property
    def path(self) -> Path:
        return self._path


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def validate_jsonl(path: Path) -> "ValidationResult":
    """Read a JSONL file and check chronological order, no duplicates, schema validity."""
    errors: list[str] = []
    timestamps: list[int] = []
    record_count = 0

    if not path.exists():
        return ValidationResult(valid=False, record_count=0, errors=["File does not exist"])

    store = JsonlStore(path)
    try:
        records = store.read_all()
    except JsonlStoreError as exc:
        return ValidationResult(valid=False, record_count=0, errors=[str(exc)])

    for i, rec in enumerate(records):
        record_count += 1
        ts = rec.timestamp

        if ts in timestamps:
            errors.append(f"Duplicate timestamp {ts} at record {i}")
        timestamps.append(ts)

        if len(timestamps) >= 2 and timestamps[-1] <= timestamps[-2]:
            errors.append(
                f"Non-chronological order at record {i}: "
                f"{timestamps[-2]} → {timestamps[-1]}"
            )

    return ValidationResult(
        valid=len(errors) == 0,
        record_count=record_count,
        errors=errors,
    )


class ValidationResult:
    def __init__(self, valid: bool, record_count: int, errors: list[str]) -> None:
        self.valid = valid
        self.record_count = record_count
        self.errors = errors

    def __repr__(self) -> str:
        return f"ValidationResult(valid={self.valid}, records={self.record_count}, errors={self.errors})"
