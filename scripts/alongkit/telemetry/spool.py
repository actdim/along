#!/usr/bin/env python3
"""
alongkit.telemetry.spool - Write-ahead log (WAL) spooler for telemetry failover.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import json
import os
from typing import Any, Dict, List, Union

from .models import Span


class Spooler:
    """
    Write-ahead log (WAL) spooler for buffering telemetry spans on disk
    when network export is unavailable.
    """

    def __init__(self, repo_root: str, run_id: str) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self.run_id = str(run_id)
        self.wal_path = os.path.join(
            self.repo_root, ".along", "telemetry", "spool", f"{self.run_id}.wal"
        )

    def append_span(self, span: Union[Span, Dict[str, Any]]) -> None:
        """
        Appends span as JSON line with flush/sync to file.
        """
        if hasattr(span, "to_dict"):
            record = span.to_dict()
        elif isinstance(span, dict):
            record = span
        else:
            record = dict(span)

        wal_dir = os.path.dirname(self.wal_path)
        os.makedirs(wal_dir, exist_ok=True)

        line = json.dumps(record, ensure_ascii=True) + "\n"
        with open(self.wal_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def read_spool(self) -> List[Dict[str, Any]]:
        """
        Reads all pending JSON lines from the WAL file.
        """
        if not os.path.isfile(self.wal_path):
            return []
        spans: List[Dict[str, Any]] = []
        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        spans.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return spans

    def clear(self) -> None:
        """
        Safely removes the WAL file when flushed.
        """
        if os.path.isfile(self.wal_path):
            try:
                os.remove(self.wal_path)
            except OSError:
                pass

    def has_spool(self) -> bool:
        """
        Returns True if the WAL file exists and is non-empty.
        """
        return os.path.isfile(self.wal_path) and os.path.getsize(self.wal_path) > 0
