#!/usr/bin/env python3
"""
alongkit.circuit - Systemic Anomaly Circuit Breaker & Human Escalation Gate.

Detects infrastructure, OS, VCS, and toolchain failures that tempt LLM agents
into destructive self-healing cascades. Trips a zero-retry hard halt and emits
standardized human remediation instructions.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import repo, textio


class AnomalyClass(str, Enum):
    CLASS_1_VCS_CORRUPTION = "Class 1 (VCS / Repository State Corruption)"
    CLASS_2_OS_CONTENTION = "Class 2 (OS & Filesystem Contention)"
    CLASS_3_GLOBAL_ENV = "Class 3 (Global Environment & Toolchain Defects)"
    CLASS_4_PROCESS_CASCADE = "Class 4 (Process Cascades & Zombie Hangs)"
    CLASS_5_SYNTAX_CHURN = "Class 5 (Syntax Churn & Self-Destructive Edit Loops)"


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    TRIPPED = "tripped"     # Breaker open, hard halt
    RESOLVED = "resolved"   # Recovered and verified


@dataclass(frozen=True)
class AnomalyMatch:
    anomaly_class: AnomalyClass
    signature: str
    detail: str
    impact: str
    remediation: Tuple[str, ...]
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_class": self.anomaly_class.value,
            "signature": self.signature,
            "detail": self.detail,
            "impact": self.impact,
            "remediation": list(self.remediation),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AnomalyMatch:
        raw_cls = data.get("anomaly_class", "")
        matched_enum = AnomalyClass.CLASS_1_VCS_CORRUPTION
        for ac in AnomalyClass:
            if ac.value == raw_cls or ac.name == raw_cls:
                matched_enum = ac
                break
        return cls(
            anomaly_class=matched_enum,
            signature=data.get("signature", ""),
            detail=data.get("detail", ""),
            impact=data.get("impact", ""),
            remediation=tuple(data.get("remediation", [])),
            timestamp=data.get("timestamp", ""),
        )


# ---------------------------------------------------------------------------
# Error Signatures & Remediation Prescriptions
# ---------------------------------------------------------------------------

REMEDIATION_CLASS_1: Tuple[str, ...] = (
    "Reload IDE Window: In VS Code, press Ctrl+Shift+P -> 'Developer: Reload Window'.",
    "Reset Git Index: In PowerShell or Bash, run: Remove-Item .git/index -ErrorAction SilentlyContinue; git reset",
    "Verify Git Status: Confirm 'git status' returns exit code 0 before resuming.",
)

REMEDIATION_CLASS_2: Tuple[str, ...] = (
    "Close external processes holding file handles (IDE locks, test runners, antivirus).",
    "Verify file system permissions and available disk space.",
    "Run 'along circuit verify' to test repository access.",
)

REMEDIATION_CLASS_3: Tuple[str, ...] = (
    "Do NOT execute global package installations (pip install -g / npm -g / choco / winget).",
    "Ensure the repository environment (e.g. .venv) is active and python executable is valid.",
    "Verify required system binaries (uv, git, python) are present on PATH.",
)

REMEDIATION_CLASS_4: Tuple[str, ...] = (
    "Inspect running background tasks and terminate orphaned processes (git.exe, node.exe, python.exe).",
    "Restart terminal or development server session.",
    "Run 'along circuit verify' to confirm command responsiveness.",
)

REMEDIATION_CLASS_5: Tuple[str, ...] = (
    "Inspect syntax errors in the failing source file.",
    "Revert speculative edits: git checkout -- <file>.",
    "Verify source compiles with 'python -m py_compile <file>' before resuming.",
)

CLASS_1_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"index file smaller than expected", re.IGNORECASE), "fatal: .git/index: index file smaller than expected"),
    (re.compile(r"bad signature", re.IGNORECASE), "fatal: .git/index: bad signature"),
    (re.compile(r"Unable to create '.*index\.lock': File exists", re.IGNORECASE), "fatal: Unable to create '.git/index.lock': File exists"),
    (re.compile(r"corrupt loose object", re.IGNORECASE), "corrupt loose object in Git repository"),
    (re.compile(r"error: inflate: data stream error", re.IGNORECASE), "data stream error in Git object database"),
    (re.compile(r"fatal: loose object .* is corrupt", re.IGNORECASE), "loose object corruption detected by Git"),
]

CLASS_2_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"The process cannot access the file because it is being used by another process", re.IGNORECASE), "Windows file sharing lock (EBUSY)"),
    (re.compile(r"sharing violation", re.IGNORECASE), "NTFS file sharing violation"),
    (re.compile(r"\[Errno 13\] Permission denied", re.IGNORECASE), "Filesystem permission denied (EACCES)"),
    (re.compile(r"Access is denied", re.IGNORECASE), "OS process or file access denied"),
    (re.compile(r"\[Errno 16\] Device or resource busy", re.IGNORECASE), "Device or resource busy (EBUSY)"),
    (re.compile(r"No space left on device", re.IGNORECASE), "Exhausted disk space"),
    (re.compile(r"There is not enough space on the disk", re.IGNORECASE), "Exhausted disk space"),
    (re.compile(r"Filename too long|\[Errno 36\] File name too long", re.IGNORECASE), "Path length limit exceeded (MAX_PATH)"),
]

CLASS_3_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?:^|[\s\\/])npm(?:\.cmd|\.exe)?\s+install\s+(-g|--global)", re.IGNORECASE), "Prohibited global npm installation"),
    (re.compile(r"(?:^|[\s\\/])pip(?:\.exe)?\s+install\s+(?!-e\s)(?!.*--target)(?!.*--user)[a-zA-Z0-9_\-]+", re.IGNORECASE), "Prohibited global pip installation"),
    (re.compile(r"(?:^|[\s\\/])python(?:\d*(?:\.\d+)?)?(?:\.exe)?\s+-m\s+pip\s+install\s+(?!-e\s)(?!.*--target)(?!.*--user)[a-zA-Z0-9_\-]+", re.IGNORECASE), "Prohibited global pip installation via python -m"),
    (re.compile(r"(?:^|[\s\\/])(choco|winget|apt-get|brew)(?:\.exe)?\s+install", re.IGNORECASE), "Prohibited system package manager installation"),
    (re.compile(r"'(uv|git|dotnet|cargo)' is not recognized", re.IGNORECASE), "Missing required system binary on Windows"),
    (re.compile(r"(uv|git|dotnet|cargo):\s*command not found", re.IGNORECASE), "Missing required system binary on POSIX"),
]

CLASS_4_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"timed out after \d+(\.\d+)?s", re.IGNORECASE), "Command execution timeout expired"),
]


def classify_anomaly(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    cmd: Optional[Union[str, Sequence[str]]] = None,
) -> Optional[AnomalyMatch]:
    """Inspect command execution results and classify into 5 Systemic Anomaly classes."""
    combined = f"{stderr}\n{stdout}"
    cmd_str = ""
    if cmd:
        if isinstance(cmd, str):
            cmd_str = cmd
        else:
            cmd_str = " ".join(str(part) for part in cmd)

    now_iso = datetime.now(timezone.utc).isoformat()

    # Check Class 1: VCS Corruption
    for pat, sig in CLASS_1_PATTERNS:
        if pat.search(combined):
            return AnomalyMatch(
                anomaly_class=AnomalyClass.CLASS_1_VCS_CORRUPTION,
                signature=sig,
                detail=combined.strip()[:300],
                impact="Continued automated modifications risk destroying working tree and Git index state.",
                remediation=REMEDIATION_CLASS_1,
                timestamp=now_iso,
            )

    # Check Class 2: OS & Filesystem Contention
    if returncode != 0:
        for pat, sig in CLASS_2_PATTERNS:
            if pat.search(combined):
                return AnomalyMatch(
                    anomaly_class=AnomalyClass.CLASS_2_OS_CONTENTION,
                    signature=sig,
                    detail=combined.strip()[:300],
                    impact="File locks or disk space limits prevent atomic file writes; speculative retries compound failure.",
                    remediation=REMEDIATION_CLASS_2,
                    timestamp=now_iso,
                )

    # Check Class 3: Global Environment & Toolchain Defects
    # Also check command string for anti-workaround prohibited commands
    if cmd_str:
        for pat, sig in CLASS_3_PATTERNS:
            if pat.search(cmd_str):
                return AnomalyMatch(
                    anomaly_class=AnomalyClass.CLASS_3_GLOBAL_ENV,
                    signature=sig,
                    detail=f"Prohibited command intercepted: {cmd_str.strip()[:200]}",
                    impact="Executing global package manager commands violates repository hermeticity and environment isolation.",
                    remediation=REMEDIATION_CLASS_3,
                    timestamp=now_iso,
                )

    if returncode != 0:
        for pat, sig in CLASS_3_PATTERNS:
            if pat.search(combined):
                return AnomalyMatch(
                    anomaly_class=AnomalyClass.CLASS_3_GLOBAL_ENV,
                    signature=sig,
                    detail=combined.strip()[:300],
                    impact="Missing toolchain binaries prevent required build/test steps; retrying within agent loop is futile.",
                    remediation=REMEDIATION_CLASS_3,
                    timestamp=now_iso,
                )

    # Check Class 4: Process Cascades & Zombie Hangs
    for pat, sig in CLASS_4_PATTERNS:
        if pat.search(combined):
            return AnomalyMatch(
                anomaly_class=AnomalyClass.CLASS_4_PROCESS_CASCADE,
                signature=sig,
                detail=combined.strip()[:300],
                impact="Process timeout or hang indicates orphaned locks or zombie child processes.",
                remediation=REMEDIATION_CLASS_4,
                timestamp=now_iso,
            )

    return None


def format_escalation_report(anomaly: AnomalyMatch) -> str:
    """Format standardized high-visibility human escalation report."""
    lines = [
        "======================================================================",
        "[CIRCUIT BREAKER TRIPPED] Systemic Environment Anomaly Detected",
        "======================================================================",
        f"Class: {anomaly.anomaly_class.value}",
        f"Signature: {anomaly.signature}",
        f"Impact: {anomaly.impact}",
        "",
        "Prescribed Human Remediation:",
    ]
    for idx, rem in enumerate(anomaly.remediation, 1):
        lines.append(f"{idx}. {rem}")
    lines.extend([
        "",
        "Agent Action: Execution halted. Awaiting human confirmation.",
        "======================================================================",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State Persistence & Management
# ---------------------------------------------------------------------------

def get_circuit_file_path(repo_root: str) -> str:
    return os.path.join(repo.state_dir(repo_root), "diagnostics", "circuit_breaker.json")


def load_circuit_state(repo_root: str) -> Dict[str, Any]:
    fpath = get_circuit_file_path(repo_root)
    if not os.path.isfile(fpath):
        return {"state": CircuitState.CLOSED.value, "anomaly": None, "history": []}
    try:
        raw = textio.read_text(fpath, strict=False)
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {"state": CircuitState.CLOSED.value, "anomaly": None, "history": []}


def save_circuit_state(repo_root: str, data: Dict[str, Any]) -> None:
    fpath = get_circuit_file_path(repo_root)
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    try:
        textio.write_text(fpath, json.dumps(data, indent=2) + "\n")
    except (OSError, UnicodeDecodeError):
        pass


def is_breaker_tripped(repo_root: str) -> bool:
    state_data = load_circuit_state(repo_root)
    return state_data.get("state") == CircuitState.TRIPPED.value


def get_breaker_state(repo_root: str) -> Tuple[CircuitState, Optional[AnomalyMatch]]:
    state_data = load_circuit_state(repo_root)
    raw_state = state_data.get("state", CircuitState.CLOSED.value)
    state = CircuitState.CLOSED
    for cs in CircuitState:
        if cs.value == raw_state:
            state = cs
            break

    anomaly = None
    raw_anomaly = state_data.get("anomaly")
    if isinstance(raw_anomaly, dict):
        anomaly = AnomalyMatch.from_dict(raw_anomaly)
    return state, anomaly


def trip_breaker(repo_root: str, anomaly: AnomalyMatch) -> str:
    """Trip the circuit breaker, write persistent state, and return the report."""
    state_data = load_circuit_state(repo_root)
    history = state_data.get("history", [])
    if not isinstance(history, list):
        history = []

    if state_data.get("anomaly"):
        history.append(state_data["anomaly"])

    state_data["state"] = CircuitState.TRIPPED.value
    state_data["anomaly"] = anomaly.to_dict()
    state_data["tripped_at"] = anomaly.timestamp or datetime.now(timezone.utc).isoformat()
    state_data["resolved_at"] = None
    state_data["history"] = history[-10:]

    save_circuit_state(repo_root, state_data)

    report = format_escalation_report(anomaly)
    print(report, file=sys.stderr)
    return report


# ---------------------------------------------------------------------------
# Pre-Flight Health Probe & Resumption
# ---------------------------------------------------------------------------

def run_health_probe(repo_root: str) -> Tuple[bool, List[str]]:
    """Verify repository and environment health prior to resetting breaker."""
    issues: List[str] = []

    # 1. Check Git Index and lock
    git_dir = os.path.join(repo_root, ".git")
    if os.path.isdir(git_dir):
        idx_path = os.path.join(git_dir, "index")
        lock_path = os.path.join(git_dir, "index.lock")

        if os.path.isfile(lock_path):
            issues.append(f"Stale git lock detected: '{lock_path}' exists.")

        if os.path.isfile(idx_path):
            try:
                size = os.path.getsize(idx_path)
                if size < 12:
                    issues.append(f"Corrupted git index: '{idx_path}' is {size} bytes (< 12 bytes).")
            except OSError as e:
                issues.append(f"Cannot read git index '{idx_path}': {e}")
        else:
            issues.append("Missing .git/index file.")

    # 2. Check Python syntax of tracked modified files
    activity_trace_path = os.path.join(repo.state_dir(repo_root), "diagnostics", "activity_trace.json")
    if os.path.isfile(activity_trace_path):
        try:
            raw = textio.read_text(activity_trace_path, strict=False)
            tdata = json.loads(raw)
            edited = tdata.get("edited_files", [])
            for ef in edited:
                full_path = os.path.join(repo_root, ef) if not os.path.isabs(ef) else ef
                if full_path.endswith(".py") and os.path.isfile(full_path):
                    try:
                        content = textio.read_text(full_path, strict=False)
                        ast.parse(content, filename=full_path)
                    except (SyntaxError, ValueError) as syn_err:
                        issues.append(f"Syntax compilation error in '{ef}': {syn_err}")
                    except (OSError, UnicodeDecodeError) as exc:
                        issues.append(f"Cannot read or parse '{ef}': {exc}")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass

    return (len(issues) == 0, issues)


def reset_breaker(repo_root: str, force: bool = False) -> Tuple[bool, str]:
    """Reset the circuit breaker after confirming environment health."""
    if not force:
        healthy, issues = run_health_probe(repo_root)
        if not healthy:
            issue_str = "\n- ".join(issues)
            return False, f"Cannot reset circuit breaker: health probe failed:\n- {issue_str}"

    state_data = load_circuit_state(repo_root)
    state_data["state"] = CircuitState.CLOSED.value
    state_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    state_data["anomaly"] = None
    save_circuit_state(repo_root, state_data)
    return True, "Circuit breaker reset successfully. Environment verified healthy."


# ---------------------------------------------------------------------------
# Syntax Churn Tracking (Class 5 Helper)
# ---------------------------------------------------------------------------

def record_syntax_failure(repo_root: str, file_path: str, error_detail: str) -> Optional[AnomalyMatch]:
    """Track compilation errors per file. Trip Class 5 if >= 2 consecutive failures."""
    trace_path = os.path.join(repo.state_dir(repo_root), "diagnostics", "syntax_churn.json")
    churn_data: Dict[str, Any] = {}
    if os.path.isfile(trace_path):
        try:
            raw = textio.read_text(trace_path, strict=False)
            churn_data = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            churn_data = {}

    rel_path = repo.normalize_posix(file_path)
    file_record = churn_data.get(rel_path, {"failures": 0, "last_error": ""})
    file_record["failures"] = file_record.get("failures", 0) + 1
    file_record["last_error"] = error_detail[:200]
    churn_data[rel_path] = file_record

    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    try:
        textio.write_text(trace_path, json.dumps(churn_data, indent=2) + "\n")
    except (OSError, UnicodeDecodeError):
        pass

    if file_record["failures"] >= 2:
        now_iso = datetime.now(timezone.utc).isoformat()
        anomaly = AnomalyMatch(
            anomaly_class=AnomalyClass.CLASS_5_SYNTAX_CHURN,
            signature=f"Consecutive syntax compilation failures on '{rel_path}' (count: {file_record['failures']})",
            detail=f"Last error: {error_detail[:200]}",
            impact="Repeated edits failed to achieve syntax validity; continued speculative editing risks code corruption.",
            remediation=REMEDIATION_CLASS_5,
            timestamp=now_iso,
        )
        trip_breaker(repo_root, anomaly)
        return anomaly
    return None


def record_syntax_success(repo_root: str, file_path: str) -> None:
    """Clear syntax failure count for a file after successful compilation."""
    trace_path = os.path.join(repo.state_dir(repo_root), "diagnostics", "syntax_churn.json")
    if not os.path.isfile(trace_path):
        return
    try:
        raw = textio.read_text(trace_path, strict=False)
        churn_data = json.loads(raw)
        rel_path = repo.normalize_posix(file_path)
        if rel_path in churn_data:
            del churn_data[rel_path]
            textio.write_text(trace_path, json.dumps(churn_data, indent=2) + "\n")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
