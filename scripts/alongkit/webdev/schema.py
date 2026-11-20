#!/usr/bin/env python3
"""alongkit.webdev.schema - JSON Schema specification and validation for declarative scenarios (REQ-9)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union
import ruamel.yaml

SCENARIO_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Along WebDev Scenario",
    "type": "object",
    "properties": {
        "meta": {
            "type": "object",
            "properties": {
                "issue": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["issue", "title"],
        },
        "services": {
            "type": "array",
            "items": {"type": "string"},
        },
        "auth": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "object"},
            },
        },
        "defaults": {
            "type": "object",
            "properties": {
                "origins": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "storage": {"type": "object"},
                "viewport": {"type": ["string", "object"]},
                "theme": {"type": "string", "enum": ["light", "dark", "system"]},
            },
        },
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "ac": {"type": "string"},
                    "matrix": {
                        "type": "object",
                        "properties": {
                            "viewport": {"type": "array", "items": {"type": "string"}},
                            "theme": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "not_run": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
                "required": ["id", "title"],
            },
        },
    },
    "required": ["meta", "checks"],
}


def get_scenario_schema() -> Dict[str, Any]:
    """Return scenario JSON Schema dictionary."""
    return SCENARIO_JSON_SCHEMA


def get_scenario_schema_json(indent: int = 2) -> str:
    """Return scenario JSON Schema as formatted JSON string."""
    return json.dumps(SCENARIO_JSON_SCHEMA, indent=indent)


def validate_scenario_dict(data: Any) -> Tuple[bool, List[str]]:
    """Validate scenario data structure against requirements."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return False, ["Scenario root must be a dictionary / object."]

    meta = data.get("meta")
    if not isinstance(meta, dict) or not meta.get("issue") or not meta.get("title"):
        errors.append("Scenario must declare 'meta' with 'issue' and 'title'.")

    checks = data.get("checks")
    if not isinstance(checks, list) or len(checks) == 0:
        errors.append("Scenario must declare at least one check under 'checks'.")
    else:
        for idx, chk in enumerate(checks):
            if not isinstance(chk, dict):
                errors.append(f"Check at index {idx} must be a dictionary.")
                continue
            if not chk.get("id"):
                errors.append(f"Check at index {idx} missing mandatory 'id'.")
            if not chk.get("title"):
                errors.append(f"Check at index {idx} missing mandatory 'title'.")

    return len(errors) == 0, errors


def load_scenario(path_or_content: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Load scenario from file path, content string, or dict (supporting YAML and JSON)."""
    if isinstance(path_or_content, dict):
        ok, errors = validate_scenario_dict(path_or_content)
        if not ok:
            raise ValueError(f"Scenario validation failed: {'; '.join(errors)}")
        return path_or_content

    raw_text = path_or_content
    if isinstance(path_or_content, str) and os.path.isfile(path_or_content):
        with open(path_or_content, "r", encoding="utf-8") as handle:
            raw_text = handle.read()

    yaml = ruamel.yaml.YAML(typ="safe")
    try:
        data = yaml.load(raw_text)
    except (ruamel.yaml.YAMLError, AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Failed to parse scenario YAML/JSON: {exc}")

    ok, errors = validate_scenario_dict(data)
    if not ok:
        raise ValueError(f"Scenario validation failed: {'; '.join(errors)}")

    return data
