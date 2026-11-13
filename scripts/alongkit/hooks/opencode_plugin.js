/**
 * along-gates.js - Along runtime lifecycle hook plugin for OpenCode.
 *
 * Supports OpenCode V2 plugin architecture (export default { id, setup }) with
 * fallback compatibility for legacy V1 loaders.
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
    output?.sessionID ||
    output?.sessionId ||
    output?.session_id ||
    event?.sessionID ||
    event?.sessionId ||
    event?.session_id ||
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
      const check = spawnSync("py", ["-3", "-V"], { timeout: 2000 });
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
  const result = runAlongHook(hookScript, "PostToolUse", payload, projectDir);
  if (result.status !== 0 && result.stderr) {
    logDiagnostic(`PostToolUse warning for ${payload.tool_name}: ${result.stderr.trim()}`);
  }
}

function handleStop(event, projectDir) {
  const hookScript = findAlongHook(projectDir);
  if (!hookScript) return;

  const sid = extractSessionId(event, null, null);
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
    const errorMsg = (result.stderr || result.stdout || "Session stop denied by Along protocol gate.").trim();
    logDiagnostic(`Stop gate denial: ${errorMsg}`);
    throw new Error(errorMsg);
  }
}

function handlePrompt(event, projectDir) {
  const hookScript = findAlongHook(projectDir);
  if (!hookScript) return;

  const sid = extractSessionId(event, null, null);
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
    output.env = output.env || {};
    injectSessionEnv(output.env, sid);
  }
}

/**
 * OpenCode V1 plugin implementation for backwards compatibility.
 */
export const AlongPlugin = async (ctx) => {
  const projectDir = ctx?.location?.directory || ctx?.directory || ctx?.worktree || process.cwd();

  return {
    "tool.execute.before": async (input, output) => handlePreTool(input, output, projectDir),
    "tool.execute.after": async (input, output) => handlePostTool(input, output, projectDir),
    "session.idle": async (event) => handleStop(event, projectDir),
    "session.stop": async (event) => handleStop(event, projectDir),
    "session.prompt": async (event) => handlePrompt(event, projectDir),
    "shell.env": async (input, output) => handleShellEnv(input, output),
    "shell.create.before": async (input, output) => handleShellEnv(input, output)
  };
};

/**
 * OpenCode V2 plugin definition (standard).
 */
const pluginDefinition = {
  id: "along-gates",
  async setup(ctx) {
    const projectDir = ctx?.location?.directory || ctx?.directory || ctx?.worktree || process.cwd();

    // 1. Tool execution interception
    if (ctx?.tool?.hook) {
      await ctx.tool.hook("execute.before", async (event, output) => {
        handlePreTool(event, output, projectDir);
      });
      await ctx.tool.hook("execute.after", async (event, output) => {
        handlePostTool(event, output, projectDir);
      });
    }

    // 2. Session lifecycle hooks
    if (ctx?.session?.hook) {
      await ctx.session.hook("idle", async (event) => {
        handleStop(event, projectDir);
      });
      await ctx.session.hook("stop", async (event) => {
        handleStop(event, projectDir);
      });
      await ctx.session.hook("prompt", async (event) => {
        handlePrompt(event, projectDir);
      });
    }

    // 3. Bus event subscription fallback for stop/idle
    if (ctx?.event?.subscribe) {
      ctx.event.subscribe(async (evt) => {
        const type = String(evt?.type || "");
        if (type === "session.idle" || type === "session.stop") {
          handleStop(evt, projectDir);
        } else if (type === "session.created" || type === "session.updated") {
          const sid = evt?.sessionID || evt?.data?.sessionID;
          if (sid) updateSessionId(sid);
        }
      });
    }

    // 4. Shell environment hooks
    if (ctx?.shell?.hook) {
      await ctx.shell.hook("env", async (input, output) => {
        handleShellEnv(input, output);
      });
      await ctx.shell.hook("create.before", async (input, output) => {
        handleShellEnv(input, output);
      });
    }
  }
};

export default pluginDefinition;
