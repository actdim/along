#!/usr/bin/env python3
"""alongkit.webdev.checklist - Natural language checklist compiler for browser verification (REQ-10)."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import ruamel.yaml

from .. import entities, frontmatter, repo, textio


CHECKLIST_ITEM_RE = re.compile(
    r"^-\s*\[([ xX])\]\s*(?:(?:(?:\*{1,2}|`|\[)?(C\d+)(?:\*{1,2}|`|\])?(?::\s*|\s+))|(?:\[(C\d+)\]\s*))?(.*)$",
    re.IGNORECASE,
)

AC_TAG_RE = re.compile(r"\b(AC[-_]\d+)\b", re.IGNORECASE)
VIEWPORT_RE = re.compile(r"\b(\d{3,4}x\d{3,4})\b")
THEME_RE = re.compile(r"\b(light|dark)\b", re.IGNORECASE)


def parse_checklist_markdown(content: str) -> List[Dict[str, Any]]:
    """Parse Markdown checklist items into structured check specifications."""
    items: List[Dict[str, Any]] = []
    auto_id_counter = 1

    for line in content.splitlines():
        line_clean = line.strip()
        match = CHECKLIST_ITEM_RE.match(line_clean)
        if not match:
            continue

        checked = match.group(1).lower() == "x"
        cid = match.group(2) or match.group(3)
        rest = match.group(4).strip()

        if not cid:
            cid = f"C{auto_id_counter}"
            auto_id_counter += 1

        # Extract AC reference if present
        ac_match = AC_TAG_RE.search(rest)
        ac_ref = ac_match.group(1).upper() if ac_match else None

        # Viewport hints
        vp_match = VIEWPORT_RE.search(rest)
        viewport_hint = None
        if vp_match:
            raw_dim = vp_match.group(1)
            # Map common dimensions to known presets or custom
            if raw_dim == "375x812":
                viewport_hint = "mobile-375x812"
            elif raw_dim == "390x844":
                viewport_hint = "mobile-390x844"
            elif raw_dim in ("1280x800", "1440x900", "1920x1080"):
                viewport_hint = f"desktop-{raw_dim}"
            else:
                viewport_hint = f"custom-{raw_dim}"

        # Theme hints
        theme_match = THEME_RE.search(rest)
        theme_hint = theme_match.group(1).lower() if theme_match else None

        items.append({
            "id": cid,
            "title": rest,
            "checked": checked,
            "ac": ac_ref,
            "viewport_hint": viewport_hint,
            "theme_hint": theme_hint,
        })

    return items


def extract_checklist_from_issue(repo_root: str, issue_key: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Find issue and extract checklist items from its ## Browser Verification section."""
    iss = entities.find_issue_by_slug(repo_root, issue_key)
    if not iss:
        raise ValueError(f"Issue '{issue_key}' not found in repository.")

    fpath = iss.get("file_path") or iss.get("path")
    if not fpath or not os.path.isfile(fpath):
        raise ValueError(f"Issue file for '{issue_key}' not found on disk.")

    content = textio.read_text(fpath)
    block = frontmatter.split(content)
    body = block.body if block else content

    # Search for ## Browser Verification or ## Browser Verification Checklist section
    m = re.search(
        r"^##\s+Browser Verification(?: Checklist)?\b(.*?)(?=(?:^## |\Z))",
        body,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not m:
        # Fallback to whole body search if specific heading not found
        section_text = body
    else:
        section_text = m.group(1)

    items = parse_checklist_markdown(section_text)
    return iss["slug"], items


def compile_checklist(
    repo_root: str,
    target: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Compile Markdown checklist (file or issue slug) into scenario skeleton (REQ-10)."""
    issue_slug = target
    items: List[Dict[str, Any]] = []

    target_path = os.path.join(repo_root, target) if not os.path.isabs(target) else target
    if os.path.isfile(target_path):
        content = textio.read_text(target_path)
        items = parse_checklist_markdown(content)
        issue_slug = os.path.splitext(os.path.basename(target))[0]
    else:
        issue_slug, items = extract_checklist_from_issue(repo_root, target)

    checks: List[Dict[str, Any]] = []
    for item in items:
        chk_def: Dict[str, Any] = {
            "id": item["id"],
            "title": item["title"],
        }
        if item.get("ac"):
            chk_def["ac"] = item["ac"]

        # Matrix hints if discovered in item description
        matrix_spec: Dict[str, List[str]] = {}
        if item.get("viewport_hint"):
            matrix_spec["viewport"] = [item["viewport_hint"]]
        if item.get("theme_hint"):
            matrix_spec["theme"] = [item["theme_hint"]]
        if matrix_spec:
            chk_def["matrix"] = matrix_spec

        # Empty steps array marked for agent completion
        chk_def["steps"] = []
        checks.append(chk_def)

    scenario_obj: Dict[str, Any] = {
        "meta": {
            "issue": issue_slug,
            "title": f"Compiled browser verification checklist for {issue_slug}",
        },
        "services": [],
        "defaults": {
            "origins": ["http://localhost:5173", "http://localhost:8000"],
            "viewport": "desktop-1280x800",
            "theme": "light",
        },
        "checks": checks,
    }

    if output_path:
        out_abs = os.path.join(repo_root, output_path) if not os.path.isabs(output_path) else output_path
        os.makedirs(os.path.dirname(out_abs), exist_ok=True)
        yaml = ruamel.yaml.YAML()
        yaml.default_flow_style = False
        with open(out_abs, "w", encoding="utf-8") as handle:
            yaml.dump(scenario_obj, handle)

    return scenario_obj


def handle_checklist_cli(args: Any) -> int:
    """CLI handler for 'along webdev checklist' (REQ-10)."""
    import io
    import json
    import sys

    repo_root = repo.find_repo_root()
    if args.action == "compile":
        try:
            scenario = compile_checklist(repo_root, args.target, output_path=args.out)
            if getattr(args, "json", False):
                print(json.dumps(scenario, indent=2))
            else:
                out_desc = args.out if args.out else "stdout"
                print(f"Compiled checklist from '{args.target}' ({len(scenario.get('checks', []))} check(s)) -> {out_desc}")
                if not args.out:
                    yaml = ruamel.yaml.YAML()
                    yaml.default_flow_style = False
                    buf = io.StringIO()
                    yaml.dump(scenario, buf)
                    print(buf.getvalue())
            return 0
        except (ValueError, OSError) as exc:
            print(f"[Error] Failed to compile checklist: {exc}", file=sys.stderr)
            return 2

    return 2
