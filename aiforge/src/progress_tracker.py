from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ProgressTracker:
    """Persist generation progress to a small JSON ledger."""

    path: Path
    completed_ids: set[str] = field(default_factory=set)
    failed_ids: set[str] = field(default_factory=set)
    retry_counts: dict[str, int] = field(default_factory=dict)
    completed_at: dict[str, str] = field(default_factory=dict)
    failed_at: dict[str, str] = field(default_factory=dict)
    updated_at: str | None = None

    @classmethod
    def load(cls, path: Path) -> "ProgressTracker":
        if not path.exists():
            return cls(path=path)

        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return cls(
            path=path,
            completed_ids=set(payload.get("completed_ids", [])),
            failed_ids=set(payload.get("failed_ids", [])),
            retry_counts={k: int(v) for k, v in payload.get("retry_counts", {}).items()},
            completed_at=dict(payload.get("completed_at", {})),
            failed_at=dict(payload.get("failed_at", {})),
            updated_at=payload.get("updated_at"),
        )

    @classmethod
    def load_or_create(cls, path: Path, metadata_path: Path | None = None) -> "ProgressTracker":
        tracker = cls.load(path)
        if metadata_path is not None and metadata_path.exists():
            tracker.hydrate_completed_from_metadata(metadata_path)
        tracker.path = path
        tracker.save()
        return tracker

    def hydrate_completed_from_metadata(self, metadata_path: Path) -> None:
        import csv

        with metadata_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                image_id = row.get("image_id")
                if image_id:
                    self.completed_ids.add(image_id)
                    self.completed_at.setdefault(image_id, self.updated_at or _now_iso())

    def should_skip(self, forged_image_id: str) -> bool:
        return forged_image_id in self.completed_ids

    def mark_completed(self, forged_image_id: str) -> None:
        self.completed_ids.add(forged_image_id)
        self.failed_ids.discard(forged_image_id)
        self.completed_at[forged_image_id] = _now_iso()
        self.updated_at = _now_iso()
        self.save()

    def mark_failed(self, forged_image_id: str) -> None:
        if forged_image_id not in self.completed_ids:
            self.failed_ids.add(forged_image_id)
            self.failed_at[forged_image_id] = _now_iso()
            self.updated_at = _now_iso()
            self.save()

    def record_retry(self, forged_image_id: str) -> None:
        self.retry_counts[forged_image_id] = self.retry_counts.get(forged_image_id, 0) + 1
        self.updated_at = _now_iso()
        self.save()

    def save(self) -> None:
        payload: dict[str, Any] = {
            "completed_ids": sorted(self.completed_ids),
            "failed_ids": sorted(self.failed_ids),
            "retry_counts": dict(sorted(self.retry_counts.items())),
            "completed_at": self.completed_at,
            "failed_at": self.failed_at,
            "updated_at": self.updated_at or _now_iso(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)
