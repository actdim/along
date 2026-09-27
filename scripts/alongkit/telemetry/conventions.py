#!/usr/bin/env python3
"""
alongkit.telemetry.conventions - Standard semantic attribute keys for telemetry.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

# ---------------------------------------------------------------------------
# Standard OpenInference Semantic Conventions
# ---------------------------------------------------------------------------
SPAN_KIND = "openinference.span.kind"
LLM_MODEL_NAME = "llm.model_name"
INPUT_VALUE = "input.value"
OUTPUT_VALUE = "output.value"

# ---------------------------------------------------------------------------
# Standard OpenTelemetry GenAI Semantic Conventions
# ---------------------------------------------------------------------------
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# ---------------------------------------------------------------------------
# Standard Process Semantic Conventions
# ---------------------------------------------------------------------------
PROCESS_COMMAND_LINE = "process.command_line"
PROCESS_PID = "process.pid"
PROCESS_EXIT_CODE = "process.exit.code"

# ---------------------------------------------------------------------------
# Tool Semantic Conventions
# ---------------------------------------------------------------------------
TOOL_NAME = "tool.name"
TOOL_PARAMETERS = "tool.parameters"

# ---------------------------------------------------------------------------
# Along Protocol Semantic Conventions
# ---------------------------------------------------------------------------
ALONG_RUN_ID = "along.run.id"
ALONG_REPO_ROOT = "along.repo.root"
ALONG_REPO_NAME = "along.repo.name"
ALONG_ISSUE_SLUG = "along.issue.slug"
ALONG_AGENT_NAME = "along.agent.name"
ALONG_OBSERVABILITY_LEVEL = "along.observability.level"
ALONG_OBSERVABILITY_SOURCES = "along.observability.sources"
ALONG_TURN_SEQ = "along.turn.seq"
ALONG_TURN_TITLE = "along.turn.title"
ALONG_TURN_PHASE = "along.turn.phase"
ALONG_TURN_RETRIES = "along.turn.retries"
ALONG_ARTIFACT_OFFLOADED = "along.artifact.offloaded"
ALONG_ARTIFACT_REF = "along.artifact.ref"
ALONG_ARTIFACT_SHA256 = "along.artifact.sha256"

# ---------------------------------------------------------------------------
# Standard Resource Attributes
# ---------------------------------------------------------------------------
SERVICE_NAME = "service.name"
