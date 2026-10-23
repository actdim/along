#!/usr/bin/env python3
"""
alongkit.handoff - Cross-runtime handoff entities, run records, claims, and brief generator.

Implements provider-agnostic file-based blackboard protocols for multi-runtime execution:
- Run records: .along/.session/<slug>/runs/<run-id>.json
- Machine-readable review verdicts: reviews/step-N.md front-matter
- Questions entity: .along/.session/<slug>/questions/<id>.md
- Claim management in state.json: claimed_by: {run_id, runtime, expires_at}
- Handoff note: handoff.md
- Brief generator: deterministic, compact, size-bounded prompt payload for roles
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along brief --help   (or: python scripts/along_exec.py brief --help)"
    )

import contextlib
import copy
from datetime import datetime, timezone, timedelta
import json
import os
import re
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from . import entities, frontmatter, proc, repo, session, textio

RUN_OUTCOMES = ("done", "fail", "needs-input", "timeout", "in-progress")
DEFECT_SEVERITIES = ("blocking", "important", "nit")
REVIEW_VERDICTS = ("pass", "fail")
QUESTION_STATUSES = ("open", "answered")
DEFAULT_CLAIM_TTL_SECONDS = 1800
DEFAULT_BRIEF_MAX_BYTES = 16384
SUPPORTED_BRIEF_ROLES = ("scout", "architect", "implementer", "reviewer")

#: Slugs, run ids and question ids become path components; anything else could leave the
#: blackboard (`run_id="../../x"`). [bug--orchestrator-review-fail-open] REQ-8
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _require_safe_id(value: Any, kind: str) -> str:
    """`value` as a plain identifier usable as one path component, or ValueError."""
    text = str(value or "").strip()
    if not _SAFE_ID.match(text) or ".." in text:
        raise ValueError(f"Invalid {kind} '{value}': expected letters, digits, '.', '_' or '-'.")
    return text


def _session_dir(repo_root: str, slug: str) -> str:
    return session.get_session_dir(repo_root, _require_safe_id(slug, "slug"))


def get_runs_dir(repo_root: str, slug: str) -> str:
    """Directory holding run records for a session."""
    return os.path.join(_session_dir(repo_root, slug), "runs")


def get_questions_dir(repo_root: str, slug: str) -> str:
    """Directory holding question entities for a session."""
    return os.path.join(_session_dir(repo_root, slug), "questions")


def get_handoff_path(repo_root: str, slug: str) -> str:
    """Path to the ephemeral handoff note markdown file."""
    return os.path.join(_session_dir(repo_root, slug), "handoff.md")


def get_review_path(repo_root: str, slug: str, step: int) -> str:
    """Path to reviews/step-N.md for a session step."""
    return os.path.join(_session_dir(repo_root, slug), "reviews", f"step-{int(step)}.md")


# ---------------------------------------------------------------------------
# 1. Run Records (.along/.session/<slug>/runs/<run-id>.json)
# ---------------------------------------------------------------------------

def create_run_record(
    repo_root: str,
    slug: str,
    run_id: str,
    role: str,
    runtime: str,
    model: Optional[str] = None,
    step: Optional[int] = None,
    start: Optional[str] = None,
) -> Dict[str, Any]:
    """Create and persist an initial in-progress run record."""
    clean_id = _require_safe_id(run_id, "run_id")
    record: Dict[str, Any] = {
        "run_id": clean_id,
        "role": role.lower().strip(),
        "runtime": runtime.strip(),
        "model": model.strip() if model else None,
        "step": step,
        "start": start or session._utc_now_iso(),
        "end": None,
        "exit_code": None,
        "outcome": "in-progress",
        "changed_files": [],
        "usage": None,
        "handoff_note": None,
    }
    save_run_record(repo_root, slug, record)
    return record


def save_run_record(repo_root: str, slug: str, record: Dict[str, Any]) -> str:
    """Persist a run record dict as formatted JSON."""
    if not str(record.get("run_id", "")).strip():
        raise ValueError("Run record must declare a non-empty 'run_id'.")
    run_id = _require_safe_id(record.get("run_id"), "run_id")
    runs_dir = get_runs_dir(repo_root, slug)
    os.makedirs(runs_dir, exist_ok=True)
    file_path = os.path.join(runs_dir, f"{run_id}.json")
    content = json.dumps(record, indent=2) + "\n"
    textio.write_text(file_path, content, newline="\n")
    return file_path


def load_run_record(repo_root: str, slug: str, run_id: str) -> Optional[Dict[str, Any]]:
    """Load a run record by run_id, or None if absent or invalid."""
    runs_dir = get_runs_dir(repo_root, slug)
    clean_id = _require_safe_id(run_id[:-5] if run_id.endswith(".json") else run_id, "run_id")
    file_path = os.path.join(runs_dir, f"{clean_id}.json")
    if not os.path.isfile(file_path):
        return None
    try:
        raw = textio.read_text(file_path, strict=True)
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def list_run_records(repo_root: str, slug: str) -> List[Dict[str, Any]]:
    """List all run records for an issue session, sorted by start time."""
    runs_dir = get_runs_dir(repo_root, slug)
    if not os.path.isdir(runs_dir):
        return []
    records: List[Dict[str, Any]] = []
    try:
        filenames = sorted(os.listdir(runs_dir))
    except OSError:
        return []
    for fname in filenames:
        if not fname.endswith(".json"):
            continue
        rec = load_run_record(repo_root, slug, fname)
        if rec:
            records.append(rec)
    records.sort(key=lambda r: (r.get("start") or "", r.get("run_id") or ""))
    return records


def finish_run_record(
    repo_root: str,
    slug: str,
    run_id: str,
    outcome: str,
    exit_code: Optional[int] = 0,
    changed_files: Optional[List[str]] = None,
    usage: Optional[Dict[str, Any]] = None,
    handoff_note: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, Any]:
    """Complete a run record with terminal outcome, exit code, changed files, and usage."""
    if outcome not in RUN_OUTCOMES:
        raise ValueError(f"Invalid run outcome '{outcome}'. Expected one of: {RUN_OUTCOMES}")
    record = load_run_record(repo_root, slug, run_id)
    if not record:
        raise ValueError(f"Run record '{run_id}' not found for slug '{slug}'.")
    record["outcome"] = outcome
    record["exit_code"] = exit_code
    record["end"] = end or session._utc_now_iso()
    if changed_files is not None:
        record["changed_files"] = list(changed_files)
    if usage is not None:
        record["usage"] = usage
    if handoff_note is not None:
        record["handoff_note"] = handoff_note
    save_run_record(repo_root, slug, record)
    return record


# ---------------------------------------------------------------------------
# 2. Machine-Readable Review Verdicts (reviews/step-N.md)
# ---------------------------------------------------------------------------

def validate_review_verdict(verdict: str, defects: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate review verdict against defect severities.

    Rules:
    - verdict must be 'pass' or 'fail'
    - defects must be a list of mappings with 'severity' and 'description'
    - if any defect is 'blocking' or 'important', verdict must be 'fail'
    - if verdict is 'fail', there must be at least one 'blocking' or 'important' defect
    - if defects contain only 'nit' (or empty), verdict must be 'pass'
    """
    errors: List[str] = []
    v = verdict.lower().strip()
    if v not in REVIEW_VERDICTS:
        errors.append(f"Invalid verdict '{verdict}'. Expected one of: {REVIEW_VERDICTS}")
    if not isinstance(defects, list):
        errors.append("Defects must be a list of defect items.")
        return False, errors

    has_severe = False
    for i, d in enumerate(defects):
        if not isinstance(d, dict):
            errors.append(f"Defect at index {i} must be a dictionary.")
            continue
        sev = str(d.get("severity", "")).lower().strip()
        if sev not in DEFECT_SEVERITIES:
            errors.append(f"Defect at index {i} has invalid severity '{sev}'. Expected: {DEFECT_SEVERITIES}")
        if not d.get("description"):
            errors.append(f"Defect at index {i} missing required 'description'.")
        if sev in ("blocking", "important"):
            has_severe = True

    if has_severe and v == "pass":
        errors.append("Verdict cannot be 'pass' when blocking or important defects are present.")
    if not has_severe and v == "fail":
        errors.append("Verdict cannot be 'fail' without at least one blocking or important defect.")

    return len(errors) == 0, errors


def parse_review_verdict(content: str, path: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    """Parse YAML front-matter from a review markdown string or file content.

    A missing `verdict` stays empty, never `pass`: a review that does not say it passed did
    not pass. [bug--orchestrator-review-fail-open] REQ-2
    """
    fm, body = frontmatter.parse(content, path=path)
    verdict = str(fm.get("verdict") or "").lower().strip()
    raw_defects = fm.get("defects", [])
    defects = list(raw_defects) if isinstance(raw_defects, list) else []
    metadata = {
        "verdict": verdict,
        "defects": defects,
    }
    return metadata, body


def write_review_verdict(
    repo_root: str,
    slug: str,
    step: int,
    verdict: str,
    defects: Optional[List[Dict[str, Any]]] = None,
    body: str = "",
) -> str:
    """Format and write reviews/step-N.md with machine-readable front-matter."""
    defect_list = list(defects) if defects is not None else []
    verdict_clean = verdict.lower().strip()
    valid, errors = validate_review_verdict(verdict_clean, defect_list)
    if not valid:
        raise ValueError(f"Invalid review verdict data: {'; '.join(errors)}")

    file_path = get_review_path(repo_root, slug, step)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    fm_data = {
        "verdict": verdict_clean,
        "defects": defect_list,
    }
    body_text = body.strip() + "\n" if body.strip() else "\n"
    rendered = frontmatter.render(fm_data, body_text)
    textio.write_text(file_path, rendered, newline="\n")
    return file_path


def load_review_verdict(repo_root: str, slug: str, step: int) -> Optional[Dict[str, Any]]:
    """Load machine-readable review verdict from reviews/step-N.md.

    None when the file is absent or does not parse. Otherwise `valid` / `errors` say whether
    the verdict passes `validate_review_verdict`; callers must not act on an invalid one.
    """
    file_path = get_review_path(repo_root, slug, step)
    if not os.path.isfile(file_path):
        return None
    try:
        content = textio.read_text(file_path, strict=True)
        fm, body = frontmatter.parse(content, path=file_path)
        verdict = str(fm.get("verdict") or "").lower().strip()
        raw_defects = fm.get("defects", [])
        # Validated as written: a non-list `defects` is an error, not an empty list.
        valid, errors = validate_review_verdict(verdict, raw_defects)
        return {
            "step": step,
            "verdict": verdict,
            "defects": list(raw_defects) if isinstance(raw_defects, list) else [],
            "valid": valid,
            "errors": errors,
            "body": body,
            "file_path": file_path,
        }
    except (OSError, UnicodeDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 3. Questions Entity (.along/.session/<slug>/questions/<id>.md)
# ---------------------------------------------------------------------------

def create_question(
    repo_root: str,
    slug: str,
    question: str,
    options: Optional[List[str]] = None,
    recommended: Optional[str] = None,
    body: str = "",
    qid: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an open question entity in .along/.session/<slug>/questions/<id>.md."""
    q_dir = get_questions_dir(repo_root, slug)
    os.makedirs(q_dir, exist_ok=True)

    if not qid:
        existing = [f for f in os.listdir(q_dir) if f.endswith(".md")]
        qid = f"q-{len(existing) + 1}"
    clean_id = _require_safe_id(qid[:-3] if qid.endswith(".md") else qid, "question id")

    file_path = os.path.join(q_dir, f"{clean_id}.md")
    now_iso = session._utc_now_iso()
    fm_data = {
        "id": clean_id,
        "status": "open",
        "question": question.strip(),
        "options": list(options) if options is not None else [],
        "recommended": recommended.strip() if recommended else None,
        "answer": None,
        "answered_by": None,
        "created_at": now_iso,
        "answered_at": None,
    }
    body_text = body.strip() + "\n" if body.strip() else "\n"
    rendered = frontmatter.render(fm_data, body_text)
    textio.write_text(file_path, rendered, newline="\n")
    return fm_data


def load_question(repo_root: str, slug: str, qid: str) -> Optional[Dict[str, Any]]:
    """Load a question entity by ID."""
    clean_id = _require_safe_id(qid[:-3] if qid.endswith(".md") else qid, "question id")
    q_dir = get_questions_dir(repo_root, slug)
    file_path = os.path.join(q_dir, f"{clean_id}.md")
    if not os.path.isfile(file_path):
        return None
    try:
        content = textio.read_text(file_path, strict=True)
        fm, body = frontmatter.parse(content, path=file_path)
        fm["body"] = body
        fm["file_path"] = file_path
        return fm
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def answer_question(
    repo_root: str,
    slug: str,
    qid: str,
    answer: str,
    answered_by: str = "operator",
) -> Dict[str, Any]:
    """Record an operator answer to a question entity."""
    q = load_question(repo_root, slug, qid)
    if not q:
        raise ValueError(f"Question '{qid}' not found for slug '{slug}'.")
    clean_id = _require_safe_id(qid[:-3] if qid.endswith(".md") else qid, "question id")
    q_dir = get_questions_dir(repo_root, slug)
    file_path = os.path.join(q_dir, f"{clean_id}.md")

    body = q.pop("body", "")
    q.pop("file_path", None)

    q["status"] = "answered"
    q["answer"] = answer.strip()
    q["answered_by"] = answered_by.strip()
    q["answered_at"] = session._utc_now_iso()

    body_text = body.strip() + "\n" if body.strip() else "\n"
    rendered = frontmatter.render(q, body_text)
    textio.write_text(file_path, rendered, newline="\n")
    q["body"] = body
    q["file_path"] = file_path
    return q


def list_questions(repo_root: str, slug: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List question entities, optionally filtered by status ('open' | 'answered')."""
    q_dir = get_questions_dir(repo_root, slug)
    if not os.path.isdir(q_dir):
        return []
    questions: List[Dict[str, Any]] = []
    try:
        filenames = sorted(os.listdir(q_dir))
    except OSError:
        return []
    for fname in filenames:
        if not fname.endswith(".md"):
            continue
        qid = fname[:-3]
        q = load_question(repo_root, slug, qid)
        if q:
            if status is None or q.get("status") == status:
                questions.append(q)
    questions.sort(key=lambda item: (item.get("created_at") or "", item.get("id") or ""))
    return questions


def has_open_questions(repo_root: str, slug: str) -> bool:
    """Return True if any question is in status 'open'."""
    return any(q.get("status") == "open" for q in list_questions(repo_root, slug, status="open"))


# ---------------------------------------------------------------------------
# 4. Claim Management in state.json (claimed_by: {run_id, runtime, expires_at})
# ---------------------------------------------------------------------------

def parse_iso_utc(ts: str) -> Optional[datetime]:
    """Parse ISO 8601 UTC timestamp string with Z or offset."""
    try:
        clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def is_claim_expired(claim: Optional[Dict[str, Any]]) -> bool:
    """Return True if claim is missing, malformed, or expires_at is past."""
    if not isinstance(claim, dict):
        return True
    exp_str = claim.get("expires_at")
    if not exp_str:
        return True
    dt = parse_iso_utc(str(exp_str))
    if dt is None:
        return True
    return datetime.now(timezone.utc) >= dt


def get_claim(repo_root: str, slug: str) -> Optional[Dict[str, Any]]:
    """Return current claimed_by structure from state.json if present."""
    st = session.load_state(repo_root, slug)
    if not st:
        return None
    claim = st.get("claimed_by")
    return claim if isinstance(claim, dict) else None


def is_claim_active(repo_root: str, slug: str) -> bool:
    """Return True if an unexpired claim exists in state.json."""
    claim = get_claim(repo_root, slug)
    return claim is not None and not is_claim_expired(claim)


CLAIM_LOCK_FILENAME = "claim.lock"
CLAIM_LOCK_TIMEOUT_SECONDS = 5.0
#: A lock file this old was left by a process that died inside the critical section.
CLAIM_LOCK_STALE_SECONDS = 30.0


@contextlib.contextmanager
def _claim_lock(repo_root: str, slug: str) -> Iterator[None]:
    """Hold `claim.lock` (created with O_EXCL) around a claim's load-check-save.

    Without it two runners can both read an expired claim and both take it.
    [bug--orchestrator-review-fail-open] REQ-5
    """
    lock_path = os.path.join(_session_dir(repo_root, slug), CLAIM_LOCK_FILENAME)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    deadline = time.monotonic() + CLAIM_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock_path) > CLAIM_LOCK_STALE_SECONDS:
                    os.remove(lock_path)
                    continue
            except OSError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Claim lock for '{slug}' is held by another process: {lock_path}")
            time.sleep(0.05)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(OSError):
            os.remove(lock_path)


def acquire_claim(
    repo_root: str,
    slug: str,
    run_id: str,
    runtime: str,
    ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
    force: bool = False,
) -> bool:
    """Acquire or renew claim on an issue session.

    Returns:
        True if claim was acquired or renewed.
        False if currently held by another active run and force is False.
    """
    with _claim_lock(repo_root, slug):
        st = session.load_state(repo_root, slug)
        if st is None:
            return False
        current = st.get("claimed_by")
        if isinstance(current, dict) and not is_claim_expired(current):
            if current.get("run_id") == run_id:
                # Heartbeat / renewal by same run
                pass
            elif not force:
                return False

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        st["claimed_by"] = {
            "run_id": run_id,
            "runtime": runtime,
            "claimed_at": session._utc_now_iso(),
            "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        session.save_state(repo_root, slug, st)
        return True


def release_claim(repo_root: str, slug: str, run_id: str, force: bool = False) -> bool:
    """Release claim if held by run_id, expired, or force is True."""
    with _claim_lock(repo_root, slug):
        st = session.load_state(repo_root, slug)
        if st is None:
            return True
        current = st.get("claimed_by")
        if not isinstance(current, dict):
            return True
        if current.get("run_id") == run_id or force or is_claim_expired(current):
            st["claimed_by"] = None
            session.save_state(repo_root, slug, st)
            return True
        return False


# ---------------------------------------------------------------------------
# 5. Handoff Note (handoff.md)
# ---------------------------------------------------------------------------

def write_handoff_note(
    repo_root: str,
    slug: str,
    done: str,
    remaining: str,
    traps: str = "",
    max_lines: int = 25,
) -> str:
    """Write an ephemeral handoff note (at most ~20-25 lines)."""
    traps_text = traps.strip() if traps.strip() else "None noted."
    lines = [
        "# Handoff Note",
        "",
        "## What Was Done",
        done.strip(),
        "",
        "## What Is Left",
        remaining.strip(),
        "",
        "## Traps & Watch-outs",
        traps_text,
        "",
    ]
    content = "\n".join(lines)
    split_lines = content.splitlines()
    if len(split_lines) > max_lines:
        content = "\n".join(split_lines[:max_lines - 1] + ["... [truncated to 20 lines]"]) + "\n"

    path = get_handoff_path(repo_root, slug)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    textio.write_text(path, content, newline="\n")
    return path


def read_handoff_note(repo_root: str, slug: str) -> Optional[str]:
    """Read contents of handoff.md if present."""
    path = get_handoff_path(repo_root, slug)
    if not os.path.isfile(path):
        return None
    try:
        return textio.read_text(path, strict=True)
    except (OSError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# 6. Brief Generator (along brief <slug> --role <role>)
# ---------------------------------------------------------------------------

def _extract_issue_goal(body: str) -> str:
    """Extract Goal or Problem section from issue body."""
    lines = body.splitlines()
    capturing = False
    captured_lines: List[str] = []

    # First attempt: search for ## Goal or ## Problem
    for line in lines:
        if line.startswith("## "):
            header = line[3:].strip().lower()
            if header in ("goal", "problem"):
                capturing = True
                continue
            elif capturing:
                break
        elif capturing:
            captured_lines.append(line)

    result = "\n".join(captured_lines).strip()
    if result:
        return result

    # Second attempt: take prose before first ## header
    pre_header: List[str] = []
    seen_first_heading = False
    for line in lines:
        if line.startswith("# "):
            seen_first_heading = True
            continue
        if line.startswith("## "):
            break
        if seen_first_heading and line.strip():
            pre_header.append(line)
    return "\n".join(pre_header).strip()


def _extract_requirements(body: str) -> str:
    """Extract Requirements section or REQ-N patterns from issue body verbatim."""
    lines = body.splitlines()
    capturing = False
    captured_lines: List[str] = []

    # Attempt 1: ## Requirements section
    for line in lines:
        if line.startswith("## "):
            header = line[3:].strip().lower()
            if header == "requirements":
                capturing = True
                continue
            elif capturing:
                break
        elif capturing:
            captured_lines.append(line)

    result = "\n".join(captured_lines).strip()
    if result:
        return result

    # Attempt 2: Match any REQ-N lines
    req_lines: List[str] = []
    for line in lines:
        if re.search(r"\bREQ-\d+\b", line):
            req_lines.append(line.strip())
    if req_lines:
        return "\n".join(req_lines)

    # Attempt 3: Look for ## What is missing section
    missing_lines: List[str] = []
    capturing_missing = False
    for line in lines:
        if line.startswith("## "):
            header = line[3:].strip().lower()
            if "missing" in header:
                capturing_missing = True
                continue
            elif capturing_missing:
                break
        elif capturing_missing:
            missing_lines.append(line)
    return "\n".join(missing_lines).strip()


def _extract_acceptance_criteria(body: str) -> str:
    """Extract Acceptance Criteria section verbatim from issue body."""
    lines = body.splitlines()
    capturing = False
    captured_lines: List[str] = []

    for line in lines:
        if line.startswith("## "):
            header = line[3:].strip().lower()
            if "acceptance criteria" in header:
                capturing = True
                continue
            elif capturing:
                break
        elif capturing:
            captured_lines.append(line)

    return "\n".join(captured_lines).strip()


def _extract_step_info(repo_root: str, slug: str) -> str:
    """Extract current step and status from session state and plan."""
    st = session.load_state(repo_root, slug)
    if not st:
        return "No active session blackboard initialized."
    step_num = st.get("current_step", 1)
    phase = st.get("phase", "execution")
    steps = st.get("steps", [])

    step_desc = f"Step {step_num} (Phase: {phase})"
    for s in steps:
        if isinstance(s, dict) and s.get("index") == step_num:
            status = s.get("status", "pending")
            desc = s.get("description") or s.get("title") or ""
            step_desc = f"Step {step_num} [{status}]: {desc}".strip()
            break

    # Check plan.md for additional step context
    plan_text = session.read_plan(repo_root, slug)
    if plan_text:
        # Search for step heading in plan
        step_pattern = re.compile(rf"^###?\s+Step\s+{step_num}[:\s](.*)$", re.IGNORECASE | re.MULTILINE)
        m = step_pattern.search(plan_text)
        if m:
            step_desc += f"\nPlan details: {m.group(1).strip()}"

    return step_desc


def _extract_adr_constraints(repo_root: str, max_items: int = 10) -> str:
    """Extract active constraints from .along/CONSTRAINTS.md."""
    constraints_path = os.path.join(repo.state_dir(repo_root), "CONSTRAINTS.md")
    if not os.path.isfile(constraints_path):
        return ""
    try:
        content = textio.read_text(constraints_path, strict=True)
    except (OSError, UnicodeDecodeError):
        return ""

    items: List[str] = []
    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("- ") or trimmed.startswith("* "):
            items.append(trimmed)
            if len(items) >= max_items:
                break
    return "\n".join(items)


def _extract_open_defects(repo_root: str, slug: str) -> str:
    """Extract open review defects from latest review or blackboard."""
    # Check latest review verdict
    st = session.load_state(repo_root, slug)
    step_num = st.get("current_step", 1) if st else 1
    review = load_review_verdict(repo_root, slug, step_num)
    if not review and step_num > 1:
        review = load_review_verdict(repo_root, slug, step_num - 1)

    defect_lines: List[str] = []
    if review and review.get("verdict") == "fail":
        for d in review.get("defects", []):
            if not isinstance(d, dict):
                continue
            sev = d.get("severity", "blocking")
            desc = d.get("description", "")
            loc = ""
            if d.get("file"):
                loc = f" in {d.get('file')}"
                if d.get("line"):
                    loc += f":{d.get('line')}"
            defect_lines.append(f"- [{sev}] {desc}{loc}")

    if defect_lines:
        return "\n".join(defect_lines)

    # Check blackboard open_defects
    bb = session.load_blackboard(repo_root, slug)
    if bb and isinstance(bb.get("open_defects"), dict):
        for k, v in sorted(bb["open_defects"].items()):
            defect_lines.append(f"- {k}: {v}")

    return "\n".join(defect_lines)


def _extract_answered_questions(repo_root: str, slug: str) -> str:
    """Extract answered questions for handoff context."""
    questions = list_questions(repo_root, slug, status="answered")
    if not questions:
        return ""
    q_lines: List[str] = []
    for q in questions:
        qid = q.get("id", "q")
        q_text = q.get("question", "")
        ans = q.get("answer", "")
        by = q.get("answered_by", "operator")
        q_lines.append(f"- Q ({qid}): {q_text}\n  Answer ({by}): {ans}")
    return "\n".join(q_lines)


def _get_git_diff_stat(repo_root: str) -> str:
    """Return compact git diff --stat for current working tree changes."""
    res = proc.git(["diff", "--stat"], cwd=repo_root)
    stat = res.stdout.strip() if res.ok else ""
    if not stat:
        # Check staged diff
        res_staged = proc.git(["diff", "--stat", "--cached"], cwd=repo_root)
        stat = res_staged.stdout.strip() if res_staged.ok else ""
    return stat


def _extract_review_policy(repo_root: str) -> str:
    """Extract review policy from root REVIEW.md if present, else default policy."""
    review_path = os.path.join(repo_root, "REVIEW.md")
    if os.path.isfile(review_path):
        try:
            return textio.read_text(review_path, strict=True).strip()
        except (OSError, UnicodeDecodeError):
            pass
    return (
        "Repository Review Policy:\n"
        "- Defect severities: blocking (must fix, halts step), important (should fix), nit (informational).\n"
        "- Verdict rule: verdict must be 'fail' if any blocking or important defects exist, 'pass' otherwise.\n"
        "- Audit diff against issue Requirements (REQ-N) and Acceptance Criteria."
    )


def _plan_guidance(repo_root: str, slug: str, role: str) -> str:
    """Where the plan lives and who may change it. [feat--pre-approved-plans]"""
    rel = repo.normalize_posix(repo.safe_relpath(session.plan_path(repo_root, slug), repo_root))
    if role in ("scout", "architect"):
        return (f"The plan lives in `{rel}` (one living file for the issue). Write the baseline there as "
                "'Step N: ...' lines mapped to the requirements.")
    return (f"The plan lives in `{rel}`. Correct it whenever the work requires, without asking anyone: append "
            f"a revision with the reason (`along plan revise {slug} --plan-file <path> --reason \"...\"`) and keep "
            f"going. Only a problem the ticket's requirements cannot absorb goes to the user: "
            f"`along plan rework {slug} --reason \"...\"`, then stop with outcome needs-input.")


def generate_brief(
    repo_root: str,
    slug: str,
    role: str,
    max_bytes: int = DEFAULT_BRIEF_MAX_BYTES,
) -> str:
    """Generate a deterministic, compact, size-bounded prompt payload for role execution."""
    role_norm = role.lower().strip()
    if role_norm not in SUPPORTED_BRIEF_ROLES:
        raise ValueError(f"Unsupported role '{role}'. Expected one of: {SUPPORTED_BRIEF_ROLES}")
    slug = _require_safe_id(slug, "slug")

    iss = entities.find_issue_by_slug(repo_root, slug)
    if not iss:
        raise ValueError(f"Issue '{slug}' not found in .along/ISSUES/ or .along/ISSUES/done/.")

    iss_path = iss["file_path"]
    try:
        raw_issue = textio.read_text(iss_path, strict=True)
        fm, issue_body = frontmatter.parse(raw_issue, path=iss_path)
    except (OSError, UnicodeDecodeError, ValueError):
        issue_body = ""
        fm = {}

    title = fm.get("title")
    if not title:
        for ln in issue_body.splitlines():
            if ln.startswith("# "):
                title = ln[2:].strip()
                break
    title = title or slug

    goal = _extract_issue_goal(issue_body)
    requirements = _extract_requirements(issue_body)
    criteria = _extract_acceptance_criteria(issue_body)
    step_info = _extract_step_info(repo_root, slug)
    constraints = _extract_adr_constraints(repo_root)
    defects = _extract_open_defects(repo_root, slug)
    questions = _extract_answered_questions(repo_root, slug)
    handoff_note = read_handoff_note(repo_root, slug)
    diff_stat = _get_git_diff_stat(repo_root)

    review_policy = None
    if role_norm == "reviewer":
        review_policy = _extract_review_policy(repo_root)

    sections = [
        f"# Handoff Brief: {role_norm.capitalize()} ({slug})",
        "",
        f"**Task**: {title}",
        "",
        "## Issue Goal",
        goal if goal else "No goal section declared.",
        "",
        "## Requirements",
        requirements if requirements else "No explicit requirements declared.",
        "",
        "## Acceptance Criteria",
        criteria if criteria else "No acceptance criteria declared.",
        "",
        "## Plan",
        _plan_guidance(repo_root, slug, role_norm),
        "",
        "## Current Step",
        step_info,
        "",
        "## Architectural Constraints",
        constraints if constraints else "No active ADR constraints.",
        "",
        "## Open Defects",
        defects if defects else "None.",
        "",
        "## Answered Questions",
        questions if questions else "None.",
        "",
        "## Last Handoff Note",
        handoff_note.strip() if handoff_note else "None.",
        "",
        "## Git Diff Stat",
        diff_stat if diff_stat else "No working tree diff.",
        "",
    ]

    if review_policy is not None:
        sections.extend([
            "## Review Policy",
            review_policy,
            "",
        ])

    payload = "\n".join(sections)
    payload_bytes = payload.encode("utf-8")
    if len(payload_bytes) > max_bytes:
        marker = "\n\n... [Brief payload truncated to stay within context budget]\n"
        marker_bytes = len(marker.encode("utf-8"))
        allowed = max(0, max_bytes - marker_bytes)
        payload = payload_bytes[:allowed].decode("utf-8", errors="ignore") + marker

    return payload
