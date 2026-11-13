/**
 * along-opencode-plugin.js - Along runtime lifecycle hook plugin for OpenCode.
 *
 * Intercepts tool calls before execution (PreToolUse) to enforce Along gates,
 * logs execution after tool completion (PostToolUse), and injects session
 * context into the shell environment (shell.env).
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

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

function runAlongHook(hookScript, eventName, payload) {
  const pyCmd = process.platform === "win32" ? "python" : "python3";
  const jsonPayload = JSON.stringify(payload);
  const args = [hookScript, "--runtime", "opencode", "--event", eventName];

  const res = spawnSync(pyCmd, args, {
    input: jsonPayload,
    encoding: "utf-8",
    maxBuffer: 10 * 1024 * 1024,
    env: { ...process.env, OPENCODE_AGENT: "1", OPENCODE_CLI: "1" }
  });

  return {
    status: res.status ?? 0,
    stdout: res.stdout || "",
    stderr: res.stderr || ""
  };
}

export const AlongPlugin = async (ctx) => {
  const projectDir = ctx?.directory || ctx?.worktree || process.cwd();

  return {
    "tool.execute.before": async (input, output) => {
      const hookScript = findAlongHook(projectDir);
      if (!hookScript) return;

      const payload = {
        hook_event_name: "PreToolUse",
        tool_name: input.tool,
        tool_args: output?.args || {},
        session_id: input.sessionID,
        cwd: projectDir,
        runtime: "opencode"
      };

      const result = runAlongHook(hookScript, "PreToolUse", payload);
      if (result.status !== 0) {
        const errorMsg = (result.stderr || result.stdout || "Operation denied by Along protocol gate.").trim();
        throw new Error(errorMsg);
      }
    },

    "tool.execute.after": async (input, output) => {
      const hookScript = findAlongHook(projectDir);
      if (!hookScript) return;

      const payload = {
        hook_event_name: "PostToolUse",
        tool_name: input.tool,
        tool_args: input.args || output?.args || {},
        session_id: input.sessionID,
        cwd: projectDir,
        runtime: "opencode"
      };

      runAlongHook(hookScript, "PostToolUse", payload);
    },

    "shell.env": async (input, output) => {
      const sessionID = input?.sessionID;
      if (sessionID) {
        output.env = output.env || {};
        output.env["OPENCODE_SESSION_ID"] = sessionID;
        output.env["ALONG_SESSION_KEY"] = `opencode--${sessionID}`;
        output.env["ALONG_SESSION_ID"] = sessionID;
        output.env["ALONG_SESSION_RUNTIME"] = "opencode";
      }
    }
  };
};

export default AlongPlugin;
