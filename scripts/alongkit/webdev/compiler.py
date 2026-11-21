#!/usr/bin/env python3
"""alongkit.webdev.compiler - Natural language scenario compiler and origin guard for WebDev."""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import schema
from .local_llm import LocalInferenceClient


ALLOWED_LOCAL_HOSTS: Tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
)

SYSTEM_PROMPT = """You are a deterministic test step compiler for Along WebDev.
Given natural language testing instructions, return a JSON array of steps adhering strictly to Along WebDev schema.
Each step MUST be an object with an 'action' field, chosen from:
- goto: {"action": "goto", "goto": "<url>"}
- click: {"action": "click", "selector": "<selector>"}
- fill: {"action": "fill", "selector": "<selector>", "value": "<text>"}
- assert_visible: {"action": "assert_visible", "selector": "<selector>"}
- screenshot: {"action": "screenshot", "path": "<filename>.png"}
- wait_for: {"action": "wait_for", "timeout_ms": <number>}

Output ONLY the raw JSON array of step objects, without markdown code fences or conversational text.
"""


class NLScenarioCompiler:
    """Compile natural language test instructions into executable Along WebDev scenarios."""

    def __init__(
        self,
        client: Optional[LocalInferenceClient] = None,
        base_url: Optional[str] = None,
        allowed_origins: Optional[Sequence[str]] = None,
    ) -> None:
        self.client = client or LocalInferenceClient()
        self.base_url = base_url.rstrip("/") if base_url else "http://localhost:3000"
        self.allowed_origins = list(allowed_origins) if allowed_origins else [self.base_url]

    def _validate_url_security(self, url: str) -> None:
        """Validate URL against allowed origin and protocol whitelist."""
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme:
            if url.startswith("/"):
                return
            raise ValueError(f"URL '{url}' missing scheme (expected http or https).")

        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"Forbidden URL scheme '{parsed.scheme}' in '{url}'. Only http/https allowed.")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError(f"Invalid host in URL '{url}'.")

        # Allow configured local hosts
        if hostname in ALLOWED_LOCAL_HOSTS:
            return

        # Check allowed origins list
        matched = False
        for allowed in self.allowed_origins:
            parsed_allowed = urllib.parse.urlparse(allowed)
            allowed_host = (parsed_allowed.hostname or "").lower()
            if hostname == allowed_host:
                matched = True
                break

        if not matched:
            raise ValueError(
                f"Navigation to origin '{parsed.scheme}://{parsed.netloc}' is forbidden by security policy. "
                f"Allowed origins: {self.allowed_origins}"
            )

    def compile_step_template(self, phrase: str) -> Optional[Dict[str, Any]]:
        """Match single instruction phrase against template regex rules."""
        text = phrase.strip()
        if not text:
            return None

        # 1. Navigation / Goto
        nav_pattern = re.compile(
            r"^(?:открой|перейди(?:\s+на|\s+по\s+адресу)?|загрузи|open|visit|go\s+to|navigate\s+to)\s+([^\s,]+)",
            re.IGNORECASE,
        )
        m = nav_pattern.match(text)
        if m:
            target = m.group(1).strip()
            if target.startswith("/"):
                target = f"{self.base_url}{target}"
            elif "://" in target or target.startswith("javascript:") or target.startswith("data:") or target.startswith("file:"):
                pass
            else:
                target = f"http://{target}"
            self._validate_url_security(target)
            return {"action": "goto", "goto": target}

        # 2. Fill / Type
        # e.g.: введи "admin" в input[name=username]  or  fill "admin" into #username
        fill_pattern_1 = re.compile(
            r"^(?:введи|напечатай|type|enter|fill)\s+[\"']([^\"']+)[\"']\s+(?:в|into|in)\s+([^\s,]+)",
            re.IGNORECASE,
        )
        m = fill_pattern_1.match(text)
        if m:
            val, selector = m.group(1), m.group(2)
            return {"action": "fill", "selector": selector, "value": val}

        # e.g.: заполни #username значением "admin"  or  fill #username with "admin"
        fill_pattern_2 = re.compile(
            r"^(?:заполни|fill)\s+([^\s,]+)\s+(?:значением|with)\s+[\"']([^\"']+)[\"']",
            re.IGNORECASE,
        )
        m = fill_pattern_2.match(text)
        if m:
            selector, val = m.group(1), m.group(2)
            return {"action": "fill", "selector": selector, "value": val}

        # 3. Click
        # e.g.: кликни по "Войти"  or  click button "Submit"  or  click #login-btn
        click_pattern = re.compile(
            r"^(?:кликни(?:\s+по|\s+на)?|нажми(?:\s+на)?|click(?:\s+on)?)\s+(?:кнопку\s+|кнопке\s+|button\s+)?([^\s,].*)$",
            re.IGNORECASE,
        )
        m = click_pattern.match(text)
        if m:
            target = m.group(1).strip()
            if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
                label = target[1:-1]
                selector = f'button:has-text("{label}")'
            else:
                selector = target
            return {"action": "click", "selector": selector}

        # 4. Assert Visible
        # e.g.: проверь, что виден .profile  or  assert .profile is visible
        assert_pattern = re.compile(
            r"^(?:проверь(?:,\s*что\s*виден|\s*видимость)?|убедись(?:,\s*что\s*виден)?|assert|verify|check)\s+(?:что\s+виден\s+|that\s+)?([^\s,].*?)(?:\s+is\s+visible)?$",
            re.IGNORECASE,
        )
        m = assert_pattern.match(text)
        if m:
            target = m.group(1).strip()
            if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
                label = target[1:-1]
                selector = f':has-text("{label}")'
            else:
                selector = target
            return {"action": "assert_visible", "selector": selector}

        # 5. Screenshot
        # e.g.: сделай скриншот login.png  or  take screenshot login.png
        shot_pattern = re.compile(
            r"^(?:сделай\s+скриншот|скриншот|take\s+screenshot|screenshot)(?:\s+(?:как\s+|as\s+)?([^\s,]+))?",
            re.IGNORECASE,
        )
        m = shot_pattern.match(text)
        if m:
            path = m.group(1) or "screenshot.png"
            if not path.endswith(".png") and not path.endswith(".jpg"):
                path = f"{path}.png"
            return {"action": "screenshot", "path": path}

        # 6. Wait
        # e.g.: подожди 2 секунды  or  wait 2 seconds
        wait_pattern = re.compile(
            r"^(?:подожди|wait)\s+(\d+)\s*(?:секунд[ы]?|сек|seconds|s)?",
            re.IGNORECASE,
        )
        m = wait_pattern.match(text)
        if m:
            seconds = int(m.group(1))
            return {"action": "wait_for", "timeout_ms": seconds * 1000}

        return None

    def compile_with_template(self, instruction: str) -> List[Dict[str, Any]]:
        """Split natural language instruction into steps using deterministic template matching."""
        # Split on newlines, semicolons, and common chaining conjunctions
        segments = re.split(r"(?:\r?\n|;|\s+затем\s+|\s+потом\s+|\s+and\s+then\s+|\s+then\s+|,(?=\s*(?:кликни|нажми|введи|проверь|сделай|click|type|fill|assert|take)))", instruction, flags=re.IGNORECASE)
        steps: List[Dict[str, Any]] = []

        for seg in segments:
            step = self.compile_step_template(seg)
            if step:
                steps.append(step)

        if not steps:
            raise ValueError(f"Could not parse any executable WebDev steps from instruction: '{instruction}'")

        return steps

    def compile(
        self,
        instruction: str,
        backend: str = "auto",
        issue_key: str = "webdev-nl",
        title: str = "Natural Language Scenario",
    ) -> Dict[str, Any]:
        """Compile natural language instruction into validated Along WebDev scenario dict."""
        steps: Optional[List[Dict[str, Any]]] = None

        if backend in ("auto", "local-http") and self.client.is_available():
            llm_output = self.client.generate(prompt=instruction, system=SYSTEM_PROMPT)
            if llm_output:
                clean_json = llm_output.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
                    clean_json = re.sub(r"\s*```$", "", clean_json)
                try:
                    parsed = json.loads(clean_json)
                    if isinstance(parsed, list) and len(parsed) > 0 and all(isinstance(s, dict) for s in parsed):
                        for s in parsed:
                            if s.get("action") == "goto" and s.get("goto"):
                                self._validate_url_security(str(s["goto"]))
                        steps = parsed
                except (json.JSONDecodeError, ValueError):
                    steps = None

        if not steps:
            steps = self.compile_with_template(instruction)

        scenario = {
            "meta": {
                "issue": issue_key,
                "title": title,
            },
            "defaults": {
                "origins": self.allowed_origins,
            },
            "checks": [
                {
                    "id": "nl-check-1",
                    "title": "Natural Language Verification",
                    "steps": steps,
                }
            ],
        }

        ok, errors = schema.validate_scenario_dict(scenario)
        if not ok:
            raise ValueError(f"Scenario compilation produced invalid schema: {'; '.join(errors)}")

        return scenario
