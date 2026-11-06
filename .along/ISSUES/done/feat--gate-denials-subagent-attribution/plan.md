# Living Plan: Subagent Attribution for Gate Denials & Unresolved Denial Reporting

## Execution Mode
Direct

## 1. Context & Technical Scrutiny
In multi-agent setups (such as Antigravity `invoke_subagent`, Claude Code subagents, or Along team orchestrations), a supervisor agent delegates specialized tasks to subagents (e.g. Codebase Researcher, Database Debugger, Image Generator).
Because subagents run within the same working directory or inherit environment markers (`ALONG_SESSION_KEY`, `ALONG_ISSUE_SLUG`), any tool call denied by a gate during a subagent's execution is recorded into the session blackboard's `open_denials` via `_record_denial_event`:
```python
open_denials.append({"id": did, "gate": gate, "digest": digest, "ts": now})
```
When the subagent finishes and control returns to the primary supervisor, `check_unresolved_denials` at Stop rejects turn completion:
```text
Turn Completion Rejected [gate: unresolved-gate-denial]: 1 tool call(s) denied by a gate in this turn are unresolved...
```

This causes significant operational problems:
1. The supervisor and the human user have no indication of *which* agent caused the denial.
2. The denial list in `along gates stats` and `along gates denials` contains only hash IDs and tool names with zero subagent context.
3. The supervisor cannot explain to the user what the subagent left undone because the denial provenance is lost.

### Technical Boundaries & Invariants
- Anti-Silent-Fallback Invariant: Subagents must NOT silently suppress denials or self-acknowledge without supervisor visibility. Denials must remain accountable to the session.
- Attribution Provenance: The adapter parsing the runtime payload must extract whatever subagent identifier exists (`subagent_id`, `role`, or child `conversationId`) and propagate it cleanly through `HookEvent`.
- Backward Compatibility: Single-agent runs without subagents must continue displaying standard denial output without clutter.

---

## 2. Requirements & Traceability
- **REQ-1 (HookEvent Attribution Fields)**: Add `agent_role: Optional[str]` and `subagent_id: Optional[str]` to `HookEvent` in `scripts/alongkit/hooks/models.py`.
- **REQ-2 (Adapter Extraction)**: Update `AntigravityAdapter` and `ClaudeAdapter` to extract subagent identifiers from incoming event payloads.
- **REQ-3 (Denial Record Enrichment)**: Update `_record_denial_event` in `scripts/alongkit/hooks/predicates.py` to store `"agent": agent_name` and `"subagent": subagent_role` in `open_denials` and event records.
- **REQ-4 (Stats & Denials Display)**: Update `gatestats.py` and `commands/gates.py` to format denials with agent tags: `[d-xyz] (subagent: researcher) tool: run_command`.
- **REQ-5 (Turn Stop Diagnostic Message)**: Update `check_unresolved_denials` to identify which subagents triggered unresolved denials.
- **REQ-6 (Hermetic Tests)**: Test suite in `tests/test_subagent_denials.py`.

---

## 3. Step-by-Step Implementation Changes

### Step 1: HookEvent & Adapter Extraction
1. In `scripts/alongkit/hooks/models.py`:
   - Add `subagent_id: Optional[str] = None` and `subagent_role: Optional[str] = None` to `HookEvent`.
2. In `scripts/alongkit/hooks/adapters/antigravity.py`:
   - Inspect `payload.get("subagent")` or `payload.get("agentRole")` or child conversation differences.
   - Populate `subagent_id` and `subagent_role` on `HookEvent`.
3. In `scripts/alongkit/hooks/adapters/claude.py`:
   - Inspect subagent tool payloads (e.g. `Agent` tool invocations or child contexts).

### Step 2: Persistence in `_record_denial_event` in `scripts/alongkit/hooks/predicates.py`
1. Extract attribution from `event`:
   - `agent_tag = event.subagent_role or event.subagent_id or event.runtime`
2. Include `agent: agent_tag` in `extra` dict passed to `session.record_event()` and in `open_denials` entries:
   ```python
   open_denials.append({
       "id": did,
       "gate": gate,
       "digest": digest,
       "ts": now,
       "agent": agent_tag,
   })
   ```

### Step 3: Reporting in `scripts/alongkit/gatestats.py` & `commands/gates.py`
1. Update `along gates denials` formatter:
   - For each denial, if `agent` is present and not main runtime:
     - Format: `[d-abc123] (subagent: {agent}) gate: {gate} tool: {tool}`.
2. In `along gates stats`:
   - Group denials by `(gate, agent)` so users and supervisors can see breakdown of denials caused by subagents versus the main agent.

### Step 4: Diagnostic Clarification in `check_unresolved_denials`
1. In `scripts/alongkit/hooks/predicates.py`:
   - Format held denials with subagent attribution:
     ```text
     Turn Completion Rejected [gate: unresolved-gate-denial]: 1 tool call(s) denied in this turn are unresolved:
       - d-1a2b3c [destructive_command] by subagent 'Codebase Researcher' (run_command)
     Inform the user what the subagent left undone, then run:
       along gates ack d-1a2b3c --note "<explanation>"
     ```

### Step 5: Hermetic Tests in `tests/test_subagent_denials.py`
1. Simulate PreToolUse denial with `subagent_role="researcher"`.
2. Verify `open_denials` carries `agent="researcher"`.
3. Verify `along gates denials` formats `(subagent: researcher)`.
4. Verify `check_unresolved_denials` rejection text cites subagent name.
5. Verify `along gates ack` settles the denial.

---

## 4. Verification Plan
1. Run hermetic tests: `python .along/scripts/test.py tests/test_subagent_denials.py`.
2. Inspect output format: `along gates denials --help`.
3. Typography check: `along sanitize`.
