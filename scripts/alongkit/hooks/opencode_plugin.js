/**
 * along-gates.js - Along runtime lifecycle hook plugin for OpenCode.
 *
 * Supports OpenCode V2 plugin architecture (export default { id, setup }) for
 * OpenCode 2.3.2+.
 *
 * Intercepts tool calls before execution (PreToolUse) to enforce Along gates,
 * logs execution after tool completion (PostToolUse), evaluates Stop gates on
 * session idle/stop events, captures user prompt turns, and injects session
 * context into shell environments.
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

let activeSessionId = process.env.OPENCODE_SESSION_ID || null;
let cachedPython = null;
const idleEvaluatedSessions = new Set();

const GUARD_SYMBOL = Symbol.for("along.gates.setupGuard");
function getSetupGuard() {
  if (!globalThis[GUARD_SYMBOL]) {
    globalThis[GUARD_SYMBOL] = {
      contexts: new WeakSet(),
      byProjectUrl: new Map(),
    };
  }
  return globalThis[GUARD_SYMBOL];
}

function updateSessionId(id) {
  if (id && typeof id === "string" && id.trim()) {
    activeSessionId = id.trim();
  }
}

function extractSessionId(input, output, event) {
  const sid = (
    input?.sessionID ||
    input?.sessionId ||
    input?.session_id ||
    input?.properties?.sessionID ||
    input?.data?.sessionID ||
    input?.info?.id ||
    output?.sessionID ||
    output?.sessionId ||
    output?.session_id ||
    output?.properties?.sessionID ||
    output?.data?.sessionID ||
    event?.sessionID ||
    event?.sessionId ||
    event?.session_id ||
    event?.properties?.sessionID ||
    event?.data?.sessionID ||
    event?.info?.id ||
    activeSessionId
  );
  if (sid) {
    updateSessionId(sid);
  }
  return sid || activeSessionId;
}

function findAlongHook(projectDir) {
  if (projectDir) {
    const local = path.join(projectDir, "scripts", "along_hook.py");
    if (fs.existsSync(local)) return local;
    const dotAlong = path.join(projectDir, ".along", "scripts", "along_hook.py");
    if (fs.existsSync(dotAlong)) return dotAlong;
  }
  const cwd = process.cwd();
  const cwdLocal = path.join(cwd, "scripts", "along_hook.py");
  if (fs.existsSync(cwdLocal)) return cwdLocal;
  const cwdDotAlong = path.join(cwd, ".along", "scripts", "along_hook.py");
  if (fs.existsSync(cwdDotAlong)) return cwdDotAlong;

  const globalHook = path.join(os.homedir(), ".along", "bin", "along_hook.py");
  if (fs.existsSync(globalHook)) return globalHook;

  return null;
}

function resolvePythonCommand(projectDir) {
  if (cachedPython) return cachedPython;

  if (process.env.ALONG_PYTHON && fs.existsSync(process.env.ALONG_PYTHON)) {
    return (cachedPython = { cmd: process.env.ALONG_PYTHON, extraArgs: [] });
  }

  const isWin = process.platform === "win32";
  const pyExe = isWin ? path.join("Scripts", "python.exe") : path.join("bin", "python");

  const candidates = [
    projectDir ? path.join(projectDir, ".along", "venv", pyExe) : null,
    path.join(os.homedir(), ".along", "venv", pyExe),
  ].filter(Boolean);

  for (const cand of candidates) {
    if (fs.existsSync(cand)) {
      return (cachedPython = { cmd: cand, extraArgs: [] });
    }
  }

  if (isWin) {
    try {
      const check = spawnSync("py", ["-3", "-V"], { timeout: 2000, windowsHide: true });
      if (check.status === 0) {
        return (cachedPython = { cmd: "py", extraArgs: ["-3"] });
      }
    } catch (e) {
      // py launcher not available
    }
  }

  return (cachedPython = { cmd: isWin ? "python" : "python3", extraArgs: [] });
}

function logDiagnostic(msg) {
  try {
    const diagDir = path.join(os.homedir(), ".along", "diagnostics");
    fs.mkdirSync(diagDir, { recursive: true });
    const logFile = path.join(diagDir, "opencode-hook.log");
    const line = `[${new Date().toISOString()}] ${msg}\n`;
    fs.appendFileSync(logFile, line, "utf8");
  } catch (e) {
    // Fail silently on logging issues
  }
}

function runAlongHook(hookScript, eventName, payload, projectDir) {
  const { cmd, extraArgs } = resolvePythonCommand(projectDir);
  const jsonPayload = JSON.stringify(payload);
  const args = [...extraArgs, hookScript, "--runtime", "opencode", "--event", eventName];

  let res;
  try {
    res = spawnSync(cmd, args, {
      input: jsonPayload,
      encoding: "utf-8",
      maxBuffer: 10 * 1024 * 1024,
      timeout: 10000,
      windowsHide: true,
      env: { ...process.env, OPENCODE_AGENT: "1", OPENCODE_CLI: "1" }
    });
  } catch (err) {
    logDiagnostic(`Spawn failed for event ${eventName}: ${err.message}`);
    return {
      status: -1,
      stdout: "",
      stderr: `Along hook process spawn failed: ${err.message}`,
      error: err
    };
  }

  if (res.error) {
    const errText = res.error.code === "ETIMEDOUT" ? "Along hook execution timed out (10s limit)" : res.error.message;
    logDiagnostic(`Process error for event ${eventName}: ${errText}`);
    return {
      status: res.status ?? -1,
      stdout: res.stdout || "",
      stderr: errText,
      error: res.error
    };
  }

  return {
    status: res.status ?? 0,
    stdout: res.stdout || "",
    stderr: res.stderr || ""
  };
}

function injectSessionEnv(envObj, sid) {
  if (!envObj || !sid) return;
  envObj["OPENCODE_SESSION_ID"] = sid;
  envObj["ALONG_SESSION_KEY"] = `opencode--${sid}`;
  envObj["ALONG_SESSION_ID"] = sid;
  envObj["ALONG_SESSION_RUNTIME"] = "opencode";
}

function buildPreToolPayload(input, output, projectDir) {
  const sid = extractSessionId(input, output, null);
  const toolName = input?.tool || input?.tool_name || "";
  const toolArgs = output?.args || input?.args || input?.input || {};
  return {
    hook_event_name: "PreToolUse",
    tool_name: toolName,
    tool_args: toolArgs,
    session_id: sid,
    cwd: projectDir,
    runtime: "opencode"
  };
}

function buildPostToolPayload(input, output, projectDir) {
  const sid = extractSessionId(input, output, null);
  const toolName = input?.tool || input?.tool_name || "";
  const toolArgs = input?.args || input?.input || output?.args || {};
  return {
    hook_event_name: "PostToolUse",
    tool_name: toolName,
    tool_args: toolArgs,
    session_id: sid,
    cwd: projectDir,
    runtime: "opencode"
  };
}

function handlePreTool(input, output, projectDir) {
  const hookScript = findAlongHook(projectDir);
  if (!hookScript) return;

  const payload = buildPreToolPayload(input, output, projectDir);
  idleEvaluatedSessions.delete(payload.session_id || "__default__");
  const result = runAlongHook(hookScript, "PreToolUse", payload, projectDir);
  if (result.status !== 0) {
    const errorMsg = (result.stderr || result.stdout || "Operation denied by Along protocol gate.").trim();
    throw new Error(errorMsg);
  }
}

function handlePostTool(input, output, projectDir) {
  const hookScript = findAlongHook(projectDir);
  if (!hookScript) return;

  const payload = buildPostToolPayload(input, output, projectDir);
  idleEvaluatedSessions.delete(payload.session_id || "__default__");
  const result = runAlongHook(hookScript, "PostToolUse", payload, projectDir);
  if (result.status !== 0 && result.stderr) {
    logDiagnostic(`PostToolUse warning for ${payload.tool_name}: ${result.stderr.trim()}`);
  }
}

function handleIdle(event, projectDir) {
  if (event?.background === true) {
    return;
  }

  const hookScript = findAlongHook(projectDir);
  if (!hookScript) return;

  const sid = extractSessionId(event, null, null);
  const dedupeKey = sid || "__default__";
  if (idleEvaluatedSessions.has(dedupeKey)) {
    return;
  }
  idleEvaluatedSessions.add(dedupeKey);

  const payload = {
    hook_event_name: "Stop",
    tool_name: "Stop",
    tool_args: {},
    session_id: sid,
    cwd: projectDir,
    runtime: "opencode"
  };

  const result = runAlongHook(hookScript, "Stop", payload, projectDir);
  if (result.status !== 0) {
    idleEvaluatedSessions.delete(dedupeKey);
    const errorMsg = (result.stderr || result.stdout || "Session stop denied by Along protocol gate.").trim();
    logDiagnostic(`Stop gate denial: ${errorMsg}`);
    throw new Error(errorMsg);
  }
}

function handlePrompt(event, projectDir) {
  const hookScript = findAlongHook(projectDir);
  if (!hookScript) return;

  const sid = extractSessionId(event, null, null);
  idleEvaluatedSessions.delete(sid || "__default__");
  const promptText = event?.prompt || event?.text || event?.message || "";
  const payload = {
    hook_event_name: "UserPromptSubmit",
    tool_name: "UserPromptSubmit",
    tool_args: { prompt: promptText },
    session_id: sid,
    cwd: projectDir,
    runtime: "opencode"
  };

  runAlongHook(hookScript, "UserPromptSubmit", payload, projectDir);
}

function handleShellEnv(input, output) {
  const sid = extractSessionId(input, output, null);
  if (sid) {
    if (output && typeof output === "object") {
      output.env = output.env || {};
      injectSessionEnv(output.env, sid);
    }
    if (input && typeof input === "object") {
      input.env = input.env || {};
      injectSessionEnv(input.env, sid);
    }
  }
}

/**
 * OpenCode V2 plugin definition (OpenCode 2.3.2+).
 */
const pluginDefinition = {
  id: "along-gates",
  async setup(ctx) {
    const projectDir = ctx?.location?.directory || ctx?.directory || ctx?.worktree || process.cwd();
    const guard = getSetupGuard();
    if (ctx && typeof ctx === "object") {
      if (guard.contexts.has(ctx)) {
        return;
      }
      const existingUrl = guard.byProjectUrl.get(projectDir);
      if (existingUrl && existingUrl !== import.meta.url) {
        logDiagnostic(`Skipping duplicate along-gates plugin at ${import.meta.url} (already registered from ${existingUrl})`);
        return;
      }
      guard.contexts.add(ctx);
      guard.byProjectUrl.set(projectDir, import.meta.url);
    }

    // 1. Tool execution interception
    if (ctx?.tool?.hook) {
      await ctx.tool.hook("execute.before", async (event, output) => {
        handlePreTool(event, output, projectDir);
      });
      await ctx.tool.hook("execute.after", async (event, output) => {
        handlePostTool(event, output, projectDir);
      });
    }

    // 2. Session lifecycle hooks (OpenCode 2.3.2+ uses experimental.idle as the idle/Stop signal)
    if (ctx?.session?.hook) {
      await ctx.session.hook("experimental.idle", async (event) => {
        handleIdle(event, projectDir);
      });
      await ctx.session.hook("prompt", async (event) => {
        handlePrompt(event, projectDir);
      });
    }

    // 3. Shell environment hooks
    if (ctx?.shell?.hook) {
      await ctx.shell.hook("create.before", async (input, output) => {
        handleShellEnv(input, output);
      });
    }
  }
};

export default pluginDefinition;
