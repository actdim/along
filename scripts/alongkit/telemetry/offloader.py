#!/usr/bin/env python3
"""
alongkit.telemetry.offloader - Artifact offloading for large payloads and command outputs.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import hashlib
import os
import time
from typing import Dict, Optional, Tuple

from .models import ArtifactRef

MIME_TYPES: Dict[str, str] = {
    "txt": "text/plain",
    "log": "text/plain",
    "json": "application/json",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "py": "text/x-python",
    "diff": "text/x-diff",
    "patch": "text/x-diff",
    "html": "text/html",
    "csv": "text/csv",
    "xml": "application/xml",
    "yaml": "application/x-yaml",
    "yml": "application/x-yaml",
}


class ArtifactOffloader:
    """
    Offloads large strings, command outputs, or payloads to disk artifacts.
    """

    def __init__(
        self,
        repo_root: str,
        run_id: str,
        max_bytes: int = 10240,
        max_lines: int = 50,
    ) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self.run_id = str(run_id)
        self.max_bytes = max_bytes
        self.max_lines = max_lines

    def maybe_offload(
        self,
        content: str,
        ext: str = "txt",
        preview_lines: int = 20,
        preview_chars: int = 1000,
        force: bool = False,
    ) -> tuple[str, Optional[ArtifactRef]]:
        """
        Conditionally offloads content to disk if it exceeds byte or line limits.
        `force=True` offloads regardless of size (raw output behind a distilled span).

        Returns (preview_text, artifact_ref) if offloaded, or (content, None) otherwise.
        """
        if not isinstance(content, str):
            content = "" if content is None else str(content)

        content_bytes = content.encode("utf-8")
        size_bytes = len(content_bytes)
        line_count = content.count("\n") + 1 if content else 0

        # Check thresholds
        if force or size_bytes > self.max_bytes or (content.count("\n") + 1) > self.max_lines:
            sha256 = hashlib.sha256(content_bytes).hexdigest()
            ext_clean = ext.lstrip(".") if ext else "txt"
            filename = f"{sha256}.{ext_clean}"
            relative_path = f".along/artifacts/{self.run_id}/{filename}"
            target_dir = os.path.join(self.repo_root, ".along", "artifacts", self.run_id)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, filename)

            # Atomic write with utf-8 encoding
            temp_path = f"{target_path}.tmp.{os.getpid()}_{time.time_ns()}"
            with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            os.replace(temp_path, target_path)

            mime_type = MIME_TYPES.get(ext_clean.lower(), "text/plain")
            artifact_ref = ArtifactRef(
                artifact_id=sha256,
                path=relative_path,
                sha256=sha256,
                size_bytes=size_bytes,
                line_count=line_count,
                mime_type=mime_type,
            )

            lines = content.split("\n")
            selected_lines = lines[:preview_lines]
            preview_body = "\n".join(selected_lines)
            if len(preview_body) > preview_chars:
                preview_body = preview_body[:preview_chars]

            preview_text = (
                f"{preview_body}\n"
                f"... [Output offloaded to {relative_path} ({size_bytes} bytes, {line_count} lines)]"
            )
            return preview_text, artifact_ref

        return content, None
