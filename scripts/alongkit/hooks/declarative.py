#!/usr/bin/env python3
"""
alongkit.hooks.declarative - Dynamic schema-driven gate loader and evaluator.

Loads gate definitions from YAML specifications, parses match criteria and rules,
and constructs executable DeclarativeGate instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import importlib
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .. import bootstrap, repo, textio
from .gates import BaseGate
from .models import GateDecision, GateResult, HookEvent, HookEventType


DEFAULT_GATES_FILE = os.path.join(os.path.dirname(__file__), "default_gates.yaml")
ENFORCEMENT_LAYERS = ("runtime", "git", "ci")


@dataclass
class DeclarativeRule:
    """Individual rule check within a gate definition."""
    rule_type: str  # 'regex_match', 'regex_forbidden', 'predicate'
    fields: List[str] = field(default_factory=list)
    pattern: Optional[re.Pattern] = None
    handler: Optional[Callable[..., Optional[str]]] = None
    handler_name: str = ""
    exclude_paths: List[str] = field(default_factory=list)
    error_message: str = "Gate condition violation."


@dataclass
class DeclarativeGateDefinition:
    """Parsed metadata for a declarative gate."""
    id: str
    title: str
    description: str
    event_type: HookEventType
    tools: List[str] = field(default_factory=list)
    match_args: Dict[str, re.Pattern] = field(default_factory=dict)
    rules: List[DeclarativeRule] = field(default_factory=list)
    #: Layers that enforce this gate: `runtime` (agent hooks), `git` (`along hooks
    #: install --git`), `ci` (`along gates check --ci`). See alongkit.gitgates.
    enforcement: List[str] = field(default_factory=lambda: ["runtime"])
    #: Gate-specific settings passed to predicate handlers as `options=` (for example
    #: `allowed_roots` / `write_scope` of workspace_containment).
    options: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


#: Keys of a gate entry that belong to the definition; every other key is an option.
_GATE_KEYS = frozenset((
    "id", "title", "description", "event", "tools", "match_args", "rule", "rules",
    "enforcement", "enabled",
))


def resolve_handler(handler_path: str) -> Callable[..., Optional[str]]:
    """Import and return callable handler from a dotted path."""
    parts = handler_path.split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid handler path: '{handler_path}'")
    mod_name = ".".join(parts[:-1])
    fn_name = parts[-1]
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name, None)
    if fn is None or not callable(fn):
        raise ValueError(f"Function '{fn_name}' not found or not callable in '{mod_name}'")
    return fn


class DeclarativeGate(BaseGate):
    """Dynamic gate evaluated against declarative rules and predicates."""

    def __init__(self, definition: DeclarativeGateDefinition, repo_root: Optional[str] = None):
        self.defn = definition
        self.name = definition.id
        self.repo_root = repo_root

    def evaluate(self, event: HookEvent) -> GateResult:
        # Event type filter
        if event.event_type != self.defn.event_type:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        # Tool name filter
        if self.defn.tools and event.tool_name not in self.defn.tools:
            return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        # Match args filter
        if self.defn.match_args:
            for arg_name, pat in self.defn.match_args.items():
                val = str(event.tool_args.get(arg_name, ""))
                if not pat.search(val):
                    return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

        effective_root = self.repo_root or event.workspace_root

        # Evaluate rules sequentially
        for rule in self.defn.rules:
            if rule.rule_type == "regex_match":
                matched = False
                for f in rule.fields:
                    val = event.tool_args.get(f)
                    if val is not None and rule.pattern and rule.pattern.search(str(val)):
                        matched = True
                        break
                if not matched:
                    return GateResult(
                        decision=GateDecision.DENY,
                        reason=rule.error_message,
                        gate_name=self.name,
                        exit_code=2,
                    )

            elif rule.rule_type == "regex_forbidden":
                for f in rule.fields:
                    val = event.tool_args.get(f)
                    if val is not None and rule.pattern and rule.pattern.search(str(val)):
                        return GateResult(
                            decision=GateDecision.DENY,
                            reason=rule.error_message,
                            gate_name=self.name,
                            exit_code=2,
                        )

            elif rule.rule_type == "predicate":
                if rule.handler:
                    extra: Dict[str, Any] = {"options": self.defn.options} if self.defn.options else {}
                    res = rule.handler(
                        event,
                        repo_root=effective_root,
                        exclude_paths=rule.exclude_paths,
                        **extra,
                    )
                    if isinstance(res, GateResult):
                        if not res.gate_name:
                            res.gate_name = self.name
                        return self._yield_to_breaker(res, event, effective_root)
                    elif res:
                        return self._yield_to_breaker(GateResult(
                            decision=GateDecision.DENY,
                            reason=str(res) or rule.error_message,
                            gate_name=self.name,
                            exit_code=2,
                        ), event, effective_root)

        return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)

    def _yield_to_breaker(self, result: GateResult, event: HookEvent,
                          repo_root: Optional[str]) -> GateResult:
        """A Stop gate does not reject the turn while the circuit breaker is tripped.

        Its demand (sync, wrap, tests) needs commands the breaker holds, so rejecting would
        trap the agent. The pending step is reported instead [bug--stop-gates-breaker-deadlock].
        """
        if event.event_type != HookEventType.STOP or result.decision != GateDecision.DENY or not repo_root:
            return result
        from .. import circuit
        if not circuit.is_breaker_tripped(repo_root):
            return result
        print(f"[Pending, circuit breaker tripped] {result.reason}", file=sys.stderr)
        return GateResult(decision=GateDecision.ALLOW, reason=result.reason, gate_name=self.name)


def parse_gate_dict(raw: Dict[str, Any]) -> DeclarativeGateDefinition:
    """Parse a single gate entry from YAML dictionary into DeclarativeGateDefinition."""
    gate_id = str(raw.get("id", "")).strip()
    if not gate_id:
        raise ValueError("Gate definition missing required 'id' field")

    title = str(raw.get("title", gate_id))
    description = str(raw.get("description", ""))
    event_str = str(raw.get("event", "PreToolUse")).strip()

    try:
        event_type = HookEventType(event_str)
    except ValueError:
        event_type = HookEventType.PRE_TOOL_USE

    tools_raw = raw.get("tools", [])
    if isinstance(tools_raw, str):
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
    elif isinstance(tools_raw, list):
        tools = [str(t).strip() for t in tools_raw if str(t).strip()]
    else:
        tools = []

    match_args_raw = raw.get("match_args", {})
    match_args: Dict[str, re.Pattern] = {}
    if isinstance(match_args_raw, dict):
        for k, pat in match_args_raw.items():
            match_args[str(k)] = re.compile(str(pat))

    rules: List[DeclarativeRule] = []

    # Can have a single 'rule' or a list of 'rules'
    raw_rules = raw.get("rules")
    if raw_rules is None:
        single_rule = raw.get("rule")
        raw_rules = [single_rule] if single_rule else []

    for r_entry in raw_rules:
        if not isinstance(r_entry, dict):
            continue
        rtype = str(r_entry.get("type", "regex_match")).strip().lower()
        err_msg = str(r_entry.get("error", "Gate condition violation."))

        fields_raw = r_entry.get("field", [])
        if isinstance(fields_raw, str):
            rfields = [fields_raw]
        elif isinstance(fields_raw, list):
            rfields = [str(f) for f in fields_raw]
        else:
            rfields = []

        pat = None
        if "pattern" in r_entry:
            pat = re.compile(str(r_entry["pattern"]))

        handler_name = str(r_entry.get("handler", ""))
        handler_fn = None
        if handler_name:
            handler_fn = resolve_handler(handler_name)

        exclude_paths = [str(p) for p in r_entry.get("exclude_paths", [])]

        rules.append(
            DeclarativeRule(
                rule_type=rtype,
                fields=rfields,
                pattern=pat,
                handler=handler_fn,
                handler_name=handler_name,
                exclude_paths=exclude_paths,
                error_message=err_msg,
            )
        )

    enforcement_raw = raw.get("enforcement", ["runtime"])
    if isinstance(enforcement_raw, str):
        enforcement_raw = [enforcement_raw]
    enforcement = [str(layer).strip().lower() for layer in enforcement_raw or [] if str(layer).strip()]
    unknown = [layer for layer in enforcement if layer not in ENFORCEMENT_LAYERS]
    if unknown:
        raise ValueError(f"Gate '{gate_id}' declares unknown enforcement layer(s): {unknown}")

    return DeclarativeGateDefinition(
        id=gate_id,
        title=title,
        description=description,
        event_type=event_type,
        tools=tools,
        match_args=match_args,
        rules=rules,
        enforcement=enforcement or ["runtime"],
        options={str(k): v for k, v in raw.items() if str(k) not in _GATE_KEYS},
        enabled=raw.get("enabled", True) is not False,
    )


def merge_override(base: DeclarativeGateDefinition, override: DeclarativeGateDefinition,
                   raw: Dict[str, Any]) -> DeclarativeGateDefinition:
    """Repo entry for a built-in gate: keys it sets win, the rest is inherited, so
    `{id: workspace_containment, allowed_roots: [...]}` only adds options."""
    return replace(
        base,
        title=override.title if "title" in raw else base.title,
        description=override.description if "description" in raw else base.description,
        tools=override.tools if "tools" in raw else base.tools,
        match_args=override.match_args if "match_args" in raw else base.match_args,
        event_type=override.event_type if "event" in raw else base.event_type,
        rules=override.rules if ("rule" in raw or "rules" in raw) else base.rules,
        enforcement=override.enforcement if "enforcement" in raw else base.enforcement,
        options={**base.options, **override.options},
        enabled=override.enabled,
    )


def load_gate_definitions(yaml_path: str) -> List[DeclarativeGateDefinition]:
    """Parse all gate definitions from a YAML file."""
    return [defn for defn, _raw in load_gate_entries(yaml_path)]


def load_gate_entries(yaml_path: str) -> List[Tuple[DeclarativeGateDefinition, Dict[str, Any]]]:
    """Parsed definitions paired with their raw YAML entries (needed to merge overrides)."""
    if not os.path.isfile(yaml_path):
        return []

    ruamel = bootstrap.require("ruamel.yaml")
    yaml = ruamel.YAML(typ="safe")
    try:
        raw_content = textio.read_text(yaml_path, strict=False)
        data = yaml.load(raw_content)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        sys.stderr.write(f"[Along Hook] Warning: Failed to parse YAML gates '{yaml_path}': {exc}\n")
        return []

    if not isinstance(data, dict):
        return []

    gates_raw = data.get("gates", [])
    if not isinstance(gates_raw, list):
        return []

    entries: List[Tuple[DeclarativeGateDefinition, Dict[str, Any]]] = []
    for entry in gates_raw:
        if isinstance(entry, dict):
            try:
                entries.append((parse_gate_dict(entry), entry))
            except (ValueError, KeyError, re.error) as exc:
                sys.stderr.write(f"[Along Hook] Warning: Skipping invalid gate entry in '{yaml_path}': {exc}\n")

    return entries


def load_declarative_gates(yaml_path: str, repo_root: Optional[str] = None) -> List[DeclarativeGate]:
    """Load gate definitions from YAML and construct DeclarativeGate instances."""
    definitions = load_gate_definitions(yaml_path)
    return [DeclarativeGate(defn, repo_root=repo_root) for defn in definitions]


def get_all_declarative_gates(repo_root: Optional[str] = None) -> List[DeclarativeGate]:
    """Assemble complete gate pipeline: default gates overridden by repo-specific gates."""
    defs_by_id: Dict[str, DeclarativeGateDefinition] = {}

    # 1. Load protocol defaults
    for defn in load_gate_definitions(DEFAULT_GATES_FILE):
        defs_by_id[defn.id] = defn

    # 2. Load repo overrides if present in .along/rules/gates.yaml. An entry for a built-in
    # gate is merged into it (so it can just add options or set `enabled: false`); a new id
    # defines a new gate.
    if repo_root:
        repo_rules_dir = os.path.join(repo.state_dir(repo_root), "rules")
        repo_gates_file = os.path.join(repo_rules_dir, "gates.yaml")
        for defn, raw in load_gate_entries(repo_gates_file):
            base = defs_by_id.get(defn.id)
            defs_by_id[defn.id] = merge_override(base, defn, raw) if base else defn

    # Gates without the runtime layer (git/CI repository-state checks) never run on tool events.
    return [DeclarativeGate(defn, repo_root=repo_root) for defn in defs_by_id.values()
            if defn.enabled and "runtime" in defn.enforcement]
