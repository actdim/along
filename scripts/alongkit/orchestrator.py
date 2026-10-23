#!/usr/bin/env python3
"""
alongkit.orchestrator - Cross-runtime supervisor orchestrator for tiered multi-agent loops.

Coordinates sequential execution across heterogeneous agent CLI runtimes:
- Role mapping configuration (scout, architect, implementer, reviewer)
- Phase 1: Scout / Research (generates brief, runs scout, asserts research.md)
- Phase 2: Architect (generates brief, runs planner, validates plan.md, approves plan in state.json)
- Phase 3 & 4 Step Loop:
  * Implementer: generates brief, executes step N, audits changed files and handoff note
  * Reviewer: generates brief with diff stat and tests, evaluates reviews/step-N.md front-matter
  * On pass: advances step in state.json
  * On fail: increments retry counter (max 3), feeds defects into subsequent prompt payload
  * On needs-input: halts loop with needs-input status
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along orchestrate --help   (or: python scripts/along_exec.py orchestrate --help)"
    )

import copy
import json
import os
import re
import signal
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from . import entities, frontmatter, handoff, proc, repo, session, textio
from .runner import BaseRunner, RunResult, get_runner

SUPPORTED_ROLES: Tuple[str, ...] = ("scout", "architect", "implementer", "reviewer")
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_TIMEOUT: int = 1800
#: The claim outlives one run by this much, so a renewal before the next run never finds it expired.
CLAIM_TTL_MARGIN_SECONDS: int = 300

DEFAULT_ROLES: Dict[str, Dict[str, Any]] = {
    "scout": {
        "runtime": "claude-code",
        "args": ["--dangerously-skip-permissions"],
    },
    "architect": {
        "runtime": "claude-code",
        "args": ["--dangerously-skip-permissions"],
    },
    "implementer": {
        "runtime": "claude-code",
        "args": ["--dangerously-skip-permissions"],
    },
    "reviewer": {
        "runtime": "claude-code",
        "args": ["--dangerously-skip-permissions"],
    },
}


def load_role_config(
    repo_root: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Load role-to-runtime configuration from repo config or defaults with overrides."""
    root = repo_root or repo.find_repo_root()
    config = copy.deepcopy(DEFAULT_ROLES)

    if root:
        state_dir = repo.state_dir(root)
        config_files = [
            os.path.join(state_dir, "config.yaml"),
            os.path.join(state_dir, "config.json"),
            os.path.join(root, "along.yaml"),
            os.path.join(root, "along.json"),
        ]
        for cpath in config_files:
            if not os.path.isfile(cpath):
                continue
            try:
                raw = textio.read_text(cpath, strict=False)
                parsed: Optional[Dict[str, Any]] = None
                if cpath.endswith((".yaml", ".yml")):
                    from . import bootstrap
                    ruamel = bootstrap.require("ruamel.yaml")
                    yaml = ruamel.YAML(typ="safe")
                    parsed = yaml.load(raw)
                else:
                    parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    orch_section = parsed.get("orchestration") or parsed.get("orchestrator")
                    if isinstance(orch_section, dict):
                        for role in SUPPORTED_ROLES:
                            val = orch_section.get(role)
                            if isinstance(val, str):
                                config[role] = {"runtime": val.strip(), "args": []}
                            elif isinstance(val, dict):
                                r_cfg = dict(val)
                                if "runtime" in r_cfg:
                                    r_cfg["runtime"] = str(r_cfg["runtime"]).strip()
                                if "args" in r_cfg and not isinstance(r_cfg["args"], list):
                                    r_cfg["args"] = [str(r_cfg["args"])]
                                config[role].update(r_cfg)
                        break
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue

    if overrides:
        for role in SUPPORTED_ROLES:
            val = overrides.get(role)
            if val:
                if isinstance(val, str):
                    config[role]["runtime"] = val.strip()
                elif isinstance(val, dict):
                    config[role].update(val)
        if overrides.get("model"):
            for role in SUPPORTED_ROLES:
                config[role]["model"] = str(overrides["model"]).strip()
        if overrides.get("timeout"):
            try:
                timeout_val = int(overrides["timeout"])
                for role in SUPPORTED_ROLES:
                    config[role]["timeout"] = timeout_val
            except (ValueError, TypeError):
                pass

    return config


def extract_steps_from_plan(plan_text: str) -> List[Dict[str, Any]]:
    """Parse steps from plan.md into structured step records."""
    steps: List[Dict[str, Any]] = []
    seen = set()
    pattern = re.compile(
        r"^(?:[-*]\s+(?:\[[\sx]\]\s+)?|#{1,4}\s+)?Step\s+(\d+)[:\s\-]+([^\n\r]+)",
        re.IGNORECASE | re.MULTILINE,
    )
    for m in pattern.finditer(plan_text or ""):
        try:
            num = int(m.group(1))
            title = m.group(2).strip()
            if num not in seen and title:
                seen.add(num)
                steps.append({
                    "step": num,
                    "title": title,
                    "status": "pending",
                    "retries": 0,
                    "started": None,
                    "completed": None,
                })
        except (ValueError, TypeError):
            continue
    steps.sort(key=lambda s: s["step"])
    return steps


def resolve_orchestrator_issue(repo_root: str, slug: Optional[str] = None) -> str:
    """Resolve active issue slug from parameter, active session binding, or in-progress issues."""
    if slug:
        clean_slug = str(slug).strip()
        iss = entities.find_issue_by_slug(repo_root, clean_slug)
        if iss:
            return str(iss["slug"])
        session_dir = session.get_session_dir(repo_root, clean_slug)
        if os.path.isdir(session_dir):
            return clean_slug
        return clean_slug

    active_slug = session.get_active_session_slug(repo_root)
    if active_slug:
        return active_slug

    issues = entities.scan_issues(repo_root, include_done=False)
    in_progress = [i for i in issues if i.get("status") == "in-progress"]
    if in_progress:
        return str(in_progress[0]["slug"])

    raise ValueError("No issue slug specified and no active in-progress issue found.")


class CrossRuntimeOrchestrator:
    """Supervises sequential multi-agent execution across heterogeneous CLI runtimes."""

    def __init__(
        self,
        repo_root: Optional[str] = None,
        slug: Optional[str] = None,
        role_config: Optional[Dict[str, Dict[str, Any]]] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: Optional[int] = None,
        dry_run: bool = False,
        force: bool = False,
        runner_factory: Optional[Callable[..., BaseRunner]] = None,
    ) -> None:
        self.repo_root = os.path.abspath(repo_root) if repo_root else (repo.find_repo_root() or os.getcwd())
        self.slug = resolve_orchestrator_issue(self.repo_root, slug)
        self.role_config = role_config or load_role_config(self.repo_root)
        self.max_retries = int(max_retries) if max_retries is not None else DEFAULT_MAX_RETRIES
        self.timeout = int(timeout) if timeout is not None else None
        self.dry_run = bool(dry_run)
        self.force = bool(force)
        self.runner_factory = runner_factory
        self.run_id = f"orch-{uuid.uuid4().hex[:12]}"
        self.active_runner: Optional[BaseRunner] = None
        self.execution_log: List[Dict[str, Any]] = []

    def _role_timeout(self, role: str) -> int:
        """Per-run timeout for `role`: role config, then the orchestrator's, then DEFAULT_TIMEOUT."""
        return int(self.role_config.get(role, {}).get("timeout") or self.timeout or DEFAULT_TIMEOUT)

    def _renew_claim(self, role: str) -> bool:
        """Take or extend this run's claim before a runner starts; False when another run holds it.

        [bug--orchestrator-review-fail-open] REQ-6
        """
        if session.load_state(self.repo_root, self.slug) is None:
            session.init_session(self.repo_root, self.slug, execution_mode="role-based")
        return handoff.acquire_claim(
            self.repo_root,
            self.slug,
            run_id=self.run_id,
            runtime="supervisor",
            ttl_seconds=self._role_timeout(role) + CLAIM_TTL_MARGIN_SECONDS,
        )

    def _claim_lost(self, phase: str, step: Optional[int] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": "blocked",
            "phase": phase,
            "reason": f"Issue '{self.slug}' is now claimed by another run; this run stopped before '{phase}'.",
        }
        if step is not None:
            result["step"] = step
        return result

    def _instantiate_runner(self, role: str) -> BaseRunner:
        """Instantiate configured runner adapter for a given role."""
        r_cfg = self.role_config.get(role, {})
        runtime = r_cfg.get("runtime", "claude-code")
        model = r_cfg.get("model")
        extra_args = r_cfg.get("args") or []
        r_timeout = self._role_timeout(role)

        factory = self.runner_factory or get_runner
        runner = factory(
            runtime=runtime,
            repo_root=self.repo_root,
            issue_slug=self.slug,
            model=model,
            timeout=r_timeout,
            extra_args=extra_args,
            dry_run=self.dry_run,
        )
        self.active_runner = runner
        return runner

    def run_scout_phase(self) -> Dict[str, Any]:
        """Execute Phase 1: Scout / Research."""
        st = session.load_state(self.repo_root, self.slug)
        if not st:
            st = session.init_session(self.repo_root, self.slug, execution_mode="role-based")

        session.set_session_phase(self.repo_root, phase="inquiry", slug=self.slug)
        brief = handoff.generate_brief(self.repo_root, self.slug, role="scout")
        if not self._renew_claim("scout"):
            return self._claim_lost("scout")
        runner = self._instantiate_runner("scout")
        record = runner.execute_run(brief=brief, role="scout", step=None, dry_run=self.dry_run)
        self.execution_log.append({"phase": "scout", "record": record})

        outcome = record.get("outcome")
        if outcome == "needs-input" or handoff.has_open_questions(self.repo_root, self.slug):
            session.update_state(self.repo_root, self.slug, status="needs-input")
            return {"phase": "scout", "status": "needs-input", "outcome": outcome}

        if outcome == "timeout":
            session.update_state(self.repo_root, self.slug, status="failed")
            return {"phase": "scout", "status": "timeout", "outcome": outcome}

        if outcome == "fail":
            session.update_state(self.repo_root, self.slug, status="failed")
            return {"phase": "scout", "status": "failed", "outcome": outcome}

        # Assert research.md exists and is populated
        session_dir = session.get_session_dir(self.repo_root, self.slug)
        research_file = os.path.join(session_dir, "research.md")
        if not self.dry_run:
            if not os.path.isfile(research_file) or os.path.getsize(research_file) == 0:
                session.update_state(self.repo_root, self.slug, status="failed")
                return {
                    "phase": "scout",
                    "status": "failed",
                    "reason": "Scout completed but research.md is missing or empty.",
                }
            content = textio.read_text(research_file, strict=False)
            if not content.strip() or session.is_scaffold_research(content):
                session.update_state(self.repo_root, self.slug, status="failed")
                return {
                    "phase": "scout",
                    "status": "failed",
                    "reason": "Scout completed but research.md contains only unpopulated scaffold.",
                }

        session.set_session_phase(self.repo_root, phase="planning", slug=self.slug)
        return {"phase": "scout", "status": "done", "outcome": "done"}

    def run_architect_phase(self) -> Dict[str, Any]:
        """Execute Phase 2: Architect / Living Plan."""
        session.set_session_phase(self.repo_root, phase="planning", slug=self.slug)
        brief = handoff.generate_brief(self.repo_root, self.slug, role="architect")
        if not self._renew_claim("architect"):
            return self._claim_lost("architect")
        runner = self._instantiate_runner("architect")
        record = runner.execute_run(brief=brief, role="architect", step=None, dry_run=self.dry_run)
        self.execution_log.append({"phase": "architect", "record": record})

        outcome = record.get("outcome")
        if outcome == "needs-input" or handoff.has_open_questions(self.repo_root, self.slug):
            session.update_state(self.repo_root, self.slug, status="needs-input")
            return {"phase": "architect", "status": "needs-input", "outcome": outcome}

        if outcome == "timeout":
            session.update_state(self.repo_root, self.slug, status="failed")
            return {"phase": "architect", "status": "timeout", "outcome": outcome}

        if outcome == "fail":
            session.update_state(self.repo_root, self.slug, status="failed")
            return {"phase": "architect", "status": "failed", "outcome": outcome}

        # Validate plan.md and requirement extraction
        plan_file = session.plan_path(self.repo_root, self.slug)
        if not self.dry_run:
            if not os.path.isfile(plan_file) or os.path.getsize(plan_file) == 0:
                session.update_state(self.repo_root, self.slug, status="failed")
                return {
                    "phase": "architect",
                    "status": "failed",
                    "reason": "Architect completed but plan.md is missing or empty.",
                }
            plan_text = textio.read_text(plan_file, strict=False)
            extracted = extract_steps_from_plan(plan_text)
            if extracted:
                st = session.load_state(self.repo_root, self.slug)
                if st:
                    st["steps"] = extracted
                    st["total_steps"] = len(extracted)
                    session.save_state(self.repo_root, self.slug, st)

        # Mark plan approved in state.json
        session.approve_plan(self.repo_root, slug=self.slug)
        st = session.load_state(self.repo_root, self.slug)
        if st:
            st["approved_by"] = "architect"
            st["plan_approved"] = True
            st["phase"] = "execution"
            session.save_state(self.repo_root, self.slug, st)

        return {"phase": "architect", "status": "done", "outcome": "done"}

    def run_issue_plan_phase(self) -> Optional[Dict[str, Any]]:
        """Use the issue's approved plan in place of the architect. [feat--pre-approved-plans]

        None when the issue has no plan yet (the architect writes one). A plan approved on this
        machine is taken as is: steps extracted, session approved, no architect run. A plan the
        user still has to approve or rework, or one approved without an approval event here,
        halts with needs-input: the orchestrator never approves it for the user.
        """
        state = session.issue_plan_state(self.repo_root, self.slug)
        if state is None:
            return None
        if not session.load_state(self.repo_root, self.slug):
            session.init_session(self.repo_root, self.slug, execution_mode="role-based")
        if state != session.PLAN_READY:
            reason = {
                session.PLAN_UNCONFIRMED: "plan_status is approved but not confirmed on this machine; "
                                          "the user must approve the plan here",
                "needs-approval": "the plan waits for the user's approval",
                "needs-rework": "the plan needs rework with the user",
            }.get(state, f"plan_status is {state}")
            session.update_state(self.repo_root, self.slug, status="needs-input")
            return {"phase": "plan", "status": "needs-input", "reason": reason}
        if self.dry_run:
            return {"phase": "plan", "status": "done", "outcome": "done"}
        extracted = extract_steps_from_plan(session.read_plan(self.repo_root, self.slug))
        st = session.load_state(self.repo_root, self.slug) or {}
        if extracted:
            st["steps"] = extracted
            st["total_steps"] = len(extracted)
        st["approved_by"] = "user (issue plan)"
        session.save_state(self.repo_root, self.slug, st)
        session.approve_plan(self.repo_root, slug=self.slug)
        session.append_trace(self.repo_root, self.slug,
                             f"plan approved (approved issue plan; approved_via: {session.APPROVED_VIA_ISSUE_PLAN})")
        self.execution_log.append({"phase": "plan", "record": {"outcome": "done", "source": "issue plan"}})
        return {"phase": "plan", "status": "done", "outcome": "done"}

    def _evaluate_review(
        self,
        step: int,
        rev_runner: BaseRunner,
        rev_record: Dict[str, Any],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """(verdict, defects) for a reviewed step; anything short of a valid `pass` fails.

        A missing, unparseable or invalid verdict is a blocking defect, never a pass.
        [bug--orchestrator-review-fail-open] REQ-1
        """
        review = handoff.load_review_verdict(self.repo_root, self.slug, step)
        if review is not None:
            if review.get("valid"):
                return review["verdict"], review.get("defects", [])
            return "fail", [{
                "severity": "blocking",
                "description": f"Review verdict for step {step} is invalid: {'; '.join(review.get('errors') or [])}",
            }]

        # No review file: the reviewer may have printed the verdict front-matter instead.
        stdout_text = rev_runner.last_result.stdout if rev_runner.last_result else ""
        try:
            fm, _ = frontmatter.parse(stdout_text or "")
        except ValueError:
            fm = {}
        if fm.get("verdict"):
            raw_d = fm.get("defects", [])
            try:
                handoff.write_review_verdict(
                    self.repo_root,
                    self.slug,
                    step=step,
                    verdict=str(fm["verdict"]),
                    defects=list(raw_d) if isinstance(raw_d, list) else raw_d,
                )
            except (ValueError, TypeError) as exc:
                return "fail", [{
                    "severity": "blocking",
                    "description": f"Reviewer output for step {step} has an invalid verdict: {exc}",
                }]
            review = handoff.load_review_verdict(self.repo_root, self.slug, step)
            if review is not None and review.get("valid"):
                return review["verdict"], review.get("defects", [])

        return "fail", [{
            "severity": "blocking",
            "description": (f"Reviewer produced no machine-readable verdict for step {step} "
                            f"(exit code {rev_record.get('exit_code')})."),
        }]

    def _record_step_failure(self, step: int, defects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Count a failed attempt of `step` and feed its defects to the next one.

        Returns the terminal `failed` result once the retry limit is exhausted, else None.
        """
        _st, retry_exhausted = session.update_state(
            self.repo_root,
            self.slug,
            current_step=step,
            increment_retry=True,
            max_retries=self.max_retries,
        )
        defect_map = {}
        for idx, d in enumerate(defects, start=1):
            sev = d.get("severity", "blocking") if isinstance(d, dict) else "blocking"
            desc = d.get("description", str(d)) if isinstance(d, dict) else str(d)
            defect_map[f"step_{step}_defect_{idx}_{sev}"] = desc
        session.patch_blackboard(self.repo_root, self.slug, {"open_defects": defect_map})

        if not retry_exhausted:
            return None
        session.update_state(
            self.repo_root,
            self.slug,
            current_step=step,
            step_status="failed",
            status="failed",
        )
        return {
            "status": "failed",
            "reason": f"Retry limit ({self.max_retries}) exhausted on step {step}",
            "current_step": step,
            "defects": defects,
        }

    def preview(self, skip_scout: bool = False, skip_architect: bool = False) -> Dict[str, Any]:
        """What a run would do, without touching the blackboard, claims or run records.

        [bug--orchestrator-review-fail-open] REQ-4
        """
        phases: List[Dict[str, Any]] = []

        def add(phase: str, role: str, step: Optional[int] = None, with_brief: bool = True) -> None:
            r_cfg = self.role_config.get(role, {})
            entry: Dict[str, Any] = {
                "phase": phase,
                "role": role,
                "runtime": r_cfg.get("runtime", "claude-code"),
                "model": r_cfg.get("model"),
                "timeout": self._role_timeout(role),
            }
            if step is not None:
                entry["step"] = step
            if with_brief:
                try:
                    entry["brief_bytes"] = len(handoff.generate_brief(self.repo_root, self.slug, role=role).encode("utf-8"))
                except (ValueError, OSError) as exc:
                    entry["brief_error"] = str(exc)
            phases.append(entry)

        if not skip_scout:
            add("scout", "scout")
        if not skip_architect:
            if session.issue_plan_state(self.repo_root, self.slug) == session.PLAN_READY:
                phases.append({"phase": "plan", "source": "approved issue plan"})
            else:
                add("architect", "architect")
        st = session.load_state(self.repo_root, self.slug) or {}
        total = int(st.get("total_steps") or 0)
        if total > 0:
            first = int(st.get("current_step") or 1)
            for step in range(first, total + 1):
                add("implementer", "implementer", step, with_brief=step == first)
                add("reviewer", "reviewer", step, with_brief=step == first)
        else:
            phases.append({"phase": "steps", "source": "read from the plan once it exists"})
        return {"status": "dry-run", "slug": self.slug, "phases": phases}

    def run_step_loop(self) -> Dict[str, Any]:
        """Execute Phase 3 & 4: Implementer & Reviewer Step Loop."""
        st = session.load_state(self.repo_root, self.slug)
        if not st:
            st = session.init_session(self.repo_root, self.slug, execution_mode="role-based")

        current_step = st.get("current_step", 1)
        total_steps = st.get("total_steps", 1)
        if total_steps <= 0:
            total_steps = 1

        while current_step <= total_steps:
            st = session.load_state(self.repo_root, self.slug)
            steps = st.get("steps", [])
            step_entry = next((s for s in steps if s.get("step") == current_step), None)
            retries = step_entry.get("retries", 0) if step_entry else 0

            if retries > self.max_retries:
                session.update_state(
                    self.repo_root,
                    self.slug,
                    current_step=current_step,
                    step_status="failed",
                    status="failed",
                )
                return {
                    "status": "failed",
                    "reason": f"Retry limit ({self.max_retries}) exhausted on step {current_step}",
                    "current_step": current_step,
                }

            # --- Implementer ---
            session.update_state(
                self.repo_root,
                self.slug,
                current_step=current_step,
                step_status="in-progress",
            )
            impl_brief = handoff.generate_brief(self.repo_root, self.slug, role="implementer")
            if not self._renew_claim("implementer"):
                return self._claim_lost("implementer", current_step)
            impl_runner = self._instantiate_runner("implementer")
            impl_record = impl_runner.execute_run(
                brief=impl_brief,
                role="implementer",
                step=current_step,
                dry_run=self.dry_run,
            )
            self.execution_log.append({
                "phase": "implementer",
                "step": current_step,
                "record": impl_record,
            })

            impl_outcome = impl_record.get("outcome")
            if impl_outcome == "needs-input" or handoff.has_open_questions(self.repo_root, self.slug):
                session.update_state(self.repo_root, self.slug, current_step=current_step, status="needs-input")
                return {
                    "status": "needs-input",
                    "phase": "implementer",
                    "step": current_step,
                    "outcome": impl_outcome,
                }

            if impl_outcome == "timeout":
                session.update_state(
                    self.repo_root,
                    self.slug,
                    current_step=current_step,
                    step_status="failed",
                    status="failed",
                )
                return {
                    "status": "timeout",
                    "phase": "implementer",
                    "step": current_step,
                    "outcome": impl_outcome,
                }

            if impl_outcome == "fail":
                # A failed implementation is a failed attempt; there is nothing to review.
                # [bug--orchestrator-review-fail-open] REQ-3
                failure = self._record_step_failure(current_step, [{
                    "severity": "blocking",
                    "description": f"Implementer run failed (exit code {impl_record.get('exit_code')}).",
                }])
                if failure:
                    return failure
                continue

            changed_files = impl_record.get("changed_files") or []
            if changed_files:
                session.patch_blackboard(self.repo_root, self.slug, {"touched_files": changed_files})

            # Check handoff.md note
            handoff_note = handoff.read_handoff_note(self.repo_root, self.slug)

            # --- Reviewer ---
            rev_brief = handoff.generate_brief(self.repo_root, self.slug, role="reviewer")
            if not self._renew_claim("reviewer"):
                return self._claim_lost("reviewer", current_step)
            rev_runner = self._instantiate_runner("reviewer")
            rev_record = rev_runner.execute_run(
                brief=rev_brief,
                role="reviewer",
                step=current_step,
                dry_run=self.dry_run,
            )
            self.execution_log.append({
                "phase": "reviewer",
                "step": current_step,
                "record": rev_record,
            })

            rev_outcome = rev_record.get("outcome")
            if rev_outcome == "needs-input" or handoff.has_open_questions(self.repo_root, self.slug):
                session.update_state(self.repo_root, self.slug, current_step=current_step, status="needs-input")
                return {
                    "status": "needs-input",
                    "phase": "reviewer",
                    "step": current_step,
                    "outcome": rev_outcome,
                }

            if rev_outcome == "timeout":
                session.update_state(
                    self.repo_root,
                    self.slug,
                    current_step=current_step,
                    step_status="failed",
                    status="failed",
                )
                return {
                    "status": "timeout",
                    "phase": "reviewer",
                    "step": current_step,
                    "outcome": rev_outcome,
                }

            verdict, defects = self._evaluate_review(current_step, rev_runner, rev_record)

            if verdict == "pass":
                session.update_state(
                    self.repo_root,
                    self.slug,
                    current_step=current_step,
                    step_status="passed",
                )
                session.patch_blackboard(self.repo_root, self.slug, {"open_defects": None})
                current_step += 1
                st = session.load_state(self.repo_root, self.slug)
                total_steps = st.get("total_steps", 1)
                if current_step > total_steps:
                    session.update_state(self.repo_root, self.slug, status="completed")
                    return {
                        "status": "completed",
                        "current_step": total_steps,
                        "total_steps": total_steps,
                    }
                else:
                    session.update_state(
                        self.repo_root,
                        self.slug,
                        current_step=current_step,
                        step_status="pending",
                    )
            else:
                failure = self._record_step_failure(current_step, defects)
                if failure:
                    return failure

        session.update_state(self.repo_root, self.slug, status="completed")
        return {
            "status": "completed",
            "current_step": current_step - 1,
            "total_steps": total_steps,
        }

    def orchestrate(
        self,
        skip_scout: bool = False,
        skip_architect: bool = False,
    ) -> Dict[str, Any]:
        """Execute complete orchestration lifecycle."""
        if self.dry_run:
            return self.preview(skip_scout=skip_scout, skip_architect=skip_architect)

        # An issue run straight from the daemon has no blackboard yet; the claim lives in it.
        if session.load_state(self.repo_root, self.slug) is None and session.issue_file(self.repo_root, self.slug):
            session.init_session(self.repo_root, self.slug, execution_mode="role-based")
        claimed = handoff.acquire_claim(
            self.repo_root,
            self.slug,
            run_id=self.run_id,
            runtime="supervisor",
            ttl_seconds=self._role_timeout("scout") + CLAIM_TTL_MARGIN_SECONDS,
            force=self.force,
        )
        if not claimed:
            return {
                "status": "blocked",
                "reason": f"Issue '{self.slug}' is currently claimed by another process in state.json.",
            }

        old_sigint = signal.getsignal(signal.SIGINT)
        old_sigterm = signal.getsignal(signal.SIGTERM) if hasattr(signal, "SIGTERM") else None

        def _cleanup_handler(signum, frame):
            # Only this run's own claim: one taken over by another run stays. REQ-6
            handoff.release_claim(self.repo_root, self.slug, run_id=self.run_id)
            if signum == signal.SIGINT and callable(old_sigint):
                old_sigint(signum, frame)
            elif old_sigterm and signum == signal.SIGTERM and callable(old_sigterm):
                old_sigterm(signum, frame)
            sys.exit(130)

        signal.signal(signal.SIGINT, _cleanup_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _cleanup_handler)

        try:
            if not skip_scout:
                scout_res = self.run_scout_phase()
                if scout_res.get("status") != "done":
                    return scout_res

            if not skip_architect:
                arch_res = self.run_issue_plan_phase() or self.run_architect_phase()
                if arch_res.get("status") != "done":
                    return arch_res

            step_res = self.run_step_loop()
            return step_res

        finally:
            handoff.release_claim(self.repo_root, self.slug, run_id=self.run_id)
            signal.signal(signal.SIGINT, old_sigint)
            if hasattr(signal, "SIGTERM") and old_sigterm:
                signal.signal(signal.SIGTERM, old_sigterm)


def run_orchestration(
    repo_root: Optional[str] = None,
    slug: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
    skip_scout: bool = False,
    skip_architect: bool = False,
    runner_factory: Optional[Callable[..., BaseRunner]] = None,
) -> Dict[str, Any]:
    """Convenience function to configure and execute orchestration."""
    role_cfg = load_role_config(repo_root, overrides=overrides)
    orch = CrossRuntimeOrchestrator(
        repo_root=repo_root,
        slug=slug,
        role_config=role_cfg,
        max_retries=max_retries,
        timeout=timeout,
        dry_run=dry_run,
        force=force,
        runner_factory=runner_factory,
    )
    return orch.orchestrate(skip_scout=skip_scout, skip_architect=skip_architect)


__all__ = [
    "CrossRuntimeOrchestrator",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_ROLES",
    "DEFAULT_TIMEOUT",
    "SUPPORTED_ROLES",
    "extract_steps_from_plan",
    "load_role_config",
    "resolve_orchestrator_issue",
    "run_orchestration",
]
