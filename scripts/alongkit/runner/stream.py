#!/usr/bin/env python3
"""alongkit.runner.stream - Process supervisor and chunked stream capture."""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import os
import subprocess
import sys
import threading
import time
from typing import Any, IO, List, Optional, Tuple


class ChunkedStreamSupervisor:
    """Process supervisor and chunked stream capture."""

    def __init__(
        self,
        process: subprocess.Popen,
        tracer: Optional[Any] = None,
        repo_root: Optional[str] = None,
        run_id: Optional[str] = None,
        chunk_size: int = 65536,
        chunk_timeout: float = 0.2,
        tee: bool = True,
    ) -> None:
        self.process = process
        self.tracer = tracer
        self.repo_root = os.path.abspath(repo_root) if repo_root is not None else os.getcwd()
        self.run_id = str(run_id) if run_id is not None else None
        self.chunk_size = int(chunk_size)
        self.chunk_timeout = float(chunk_timeout)
        self.tee = bool(tee)

        self._stdout_chunks: List[str] = []
        self._stderr_chunks: List[str] = []
        self._lock = threading.Lock()

        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._started = False
        self._logs_saved = False

    def start(self) -> None:
        """Launch stdout and stderr reader threads."""
        if self._started:
            return
        self._stdout_thread = threading.Thread(
            target=self._reader_loop,
            args=(self.process.stdout, "stdout"),
            name="along-stream-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._reader_loop,
            args=(self.process.stderr, "stderr"),
            name="along-stream-stderr",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        self._started = True

    def wait(self, timeout: Optional[float] = None) -> int:
        """Wait for the child process and reader threads to finish."""
        if not self._started:
            self.start()

        if timeout is not None:
            deadline = time.monotonic() + timeout
            self.process.wait(timeout=timeout)
            if self._stdout_thread is not None and self._stdout_thread.is_alive():
                remaining = max(0.0, deadline - time.monotonic())
                self._stdout_thread.join(timeout=remaining)
            if self._stderr_thread is not None and self._stderr_thread.is_alive():
                remaining = max(0.0, deadline - time.monotonic())
                self._stderr_thread.join(timeout=remaining)
        else:
            self.process.wait()
            if self._stdout_thread is not None and self._stdout_thread.is_alive():
                self._stdout_thread.join()
            if self._stderr_thread is not None and self._stderr_thread.is_alive():
                self._stderr_thread.join()

        self._save_logs()
        return 0 if self.process.returncode is None else self.process.returncode

    def get_logs(self) -> Tuple[str, str]:
        """Return accumulated (stdout, stderr) strings."""
        with self._lock:
            return ("".join(self._stdout_chunks), "".join(self._stderr_chunks))

    def _save_logs(self) -> None:
        """Save raw stdout and stderr logs to artifacts directory if run_id is set."""
        if not self.run_id or self._logs_saved:
            return
        try:
            target_dir = os.path.join(self.repo_root, ".along", "artifacts", self.run_id)
            os.makedirs(target_dir, exist_ok=True)
            stdout_content, stderr_content = self.get_logs()
            stdout_path = os.path.join(target_dir, "stdout.log")
            stderr_path = os.path.join(target_dir, "stderr.log")
            with open(stdout_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(stdout_content)
            with open(stderr_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(stderr_content)
            self._logs_saved = True
        except OSError:
            pass

    def _reader_loop(self, stream: Optional[IO[bytes]], label: str) -> None:
        """Read bytes from stream, chunk and flush periodically or on size limit."""
        if stream is None:
            return

        buf = bytearray()
        last_flush_time = time.monotonic()

        def _flush(chunk_bytes: bytes) -> None:
            if not chunk_bytes:
                return
            decoded = chunk_bytes.decode("utf-8", errors="replace")

            if self.tee:
                out = sys.stdout if label == "stdout" else sys.stderr
                try:
                    buf_stream = getattr(out, "buffer", None)
                    if buf_stream is not None:
                        buf_stream.write(chunk_bytes)
                        buf_stream.flush()
                    else:
                        out.write(decoded)
                        out.flush()
                except (OSError, UnicodeEncodeError):
                    pass

            with self._lock:
                if self.tracer is not None:
                    try:
                        active_fn = getattr(self.tracer, "active_span", None)
                        span = active_fn() if callable(active_fn) else active_fn
                        if span is not None and hasattr(span, "add_event"):
                            span.add_event(
                                f"{label}.chunk",
                                attributes={
                                    "stream": label,
                                    "bytes": len(chunk_bytes),
                                    "text_preview": decoded[:200],
                                },
                            )
                    except (OSError, RuntimeError, ValueError, AttributeError, TypeError):
                        pass

                if label == "stdout":
                    self._stdout_chunks.append(decoded)
                else:
                    self._stderr_chunks.append(decoded)

        try:
            while True:
                try:
                    if hasattr(stream, "read1"):
                        chunk = stream.read1(4096)
                    else:
                        chunk = stream.read(4096)
                except (OSError, ValueError):
                    chunk = b""

                if not chunk:
                    # EOF or closed stream
                    if buf:
                        _flush(bytes(buf))
                        buf.clear()
                    break

                buf.extend(chunk)
                while len(buf) >= self.chunk_size:
                    to_flush = bytes(buf[: self.chunk_size])
                    del buf[: self.chunk_size]
                    _flush(to_flush)
                    last_flush_time = time.monotonic()

                elapsed = time.monotonic() - last_flush_time
                if elapsed >= self.chunk_timeout and len(buf) > 0:
                    _flush(bytes(buf))
                    buf.clear()
                    last_flush_time = time.monotonic()
        finally:
            try:
                stream.close()
            except (OSError, ValueError):
                pass
