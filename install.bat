@echo off
REM install.bat - double-click / CLI wrapper around install.ps1.
REM   install.bat                   install into ALL (Claude Code + Codex + OpenCode + Antigravity), copy
REM   install.bat -Target claude    one provider: claude | codex | opencode | antigravity | both | all
REM   install.bat -Symlink          symlink skill folders instead of copy (needs admin / Developer Mode)
REM   install.bat -Uninstall        remove exactly the files the install manifest records
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause

