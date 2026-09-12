#!/usr/bin/env python3
"""
alongkit.hooks.declarative - Dynamic schema-driven gate loader and evaluator.

Loads gate definitions from YAML specifications, parses match criteria and rules,
and constructs executable DeclarativeGate instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .. import bootstrap, repo, textio
from .gates import BaseGate
from .models import GateDecision, GateResult, HookEvent, HookEventType


DEFAULT_GATES_FILE = os.path.join(os.path.dirname(__file__), "default_gates.yaml")


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
                    err = rule.handler(
                        event,
                        repo_root=effective_root,
                        exclude_paths=rule.exclude_paths,
                    )
                    if err:
                        return GateResult(
                            decision=GateDecision.DENY,
                            reason=err or rule.error_message,
                            gate_name=self.name,
                            exit_code=2,
                        )

        return GateResult(decision=GateDecision.ALLOW, gate_name=self.name)


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

    return DeclarativeGateDefinition(
        id=gate_id,
        title=title,
        description=description,
        event_type=event_type,
        tools=tools,
        match_args=match_args,
        rules=rules,
    )


def load_gate_definitions(yaml_path: str) -> List[DeclarativeGateDefinition]:
    """Parse all gate definitions from a YAML file."""
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

    definitions: List[DeclarativeGateDefinition] = []
    for entry in gates_raw:
        if isinstance(entry, dict):
            try:
                definitions.append(parse_gate_dict(entry))
            except (ValueError, KeyError, re.error) as exc:
                sys.stderr.write(f"[Along Hook] Warning: Skipping invalid gate entry in '{yaml_path}': {exc}\n")

    return definitions


def load_declarative_gates(yaml_path: str, repo_root: Optional[str] = None) -> List[DeclarativeGate]:
    """Load gate definitions from YAML and construct DeclarativeGate instances."""
    definitions = load_gate_definitions(yaml_path)
    return [DeclarativeGate(defn, repo_root=repo_root) for defn in definitions]


def get_all_declarative_gates(repo_root: Optional[str] = None) -> List[DeclarativeGate]:
    """Assemble complete gate pipeline: default gates overridden by repo-specific gates."""
    gates_by_id: Dict[str, DeclarativeGate] = {}

    # 1. Load protocol defaults
    if os.path.isfile(DEFAULT_GATES_FILE):
        for gate in load_declarative_gates(DEFAULT_GATES_FILE, repo_root=repo_root):
            gates_by_id[gate.name] = gate

    # 2. Load repo overrides if present in .along/rules/gates.yaml
    if repo_root:
        repo_rules_dir = os.path.join(repo.state_dir(repo_root), "rules")
        repo_gates_file = os.path.join(repo_rules_dir, "gates.yaml")
        if os.path.isfile(repo_gates_file):
            for gate in load_declarative_gates(repo_gates_file, repo_root=repo_root):
                gates_by_id[gate.name] = gate

    return list(gates_by_id.values())
