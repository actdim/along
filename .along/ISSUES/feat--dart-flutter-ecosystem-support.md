---
protocol: along
protocol_version: "4.1.0"
slug: dart-flutter-ecosystem-support
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [dart, flutter, mobile, multiplatform, rules, dep-scan, lifecycle]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Dart & Flutter Ecosystem Support (Rules, Dep-Scan & Lifecycle)

## Goal
Provide full Along protocol support for Dart and Flutter development, covering language and platform guidelines, pub dependency tree scanning with cache resolution, and automated lifecycle hook detection.

## Problem Statement
Flutter and Dart are standard cross-platform frameworks for mobile (iOS/Android), desktop, and web applications. Along currently does not recognize `pubspec.yaml`, offers no rules for Dart idioms or Flutter state management / widget architecture, does not scan the `.pub-cache` directory for package instructions, and cannot synthesize test or build hooks for Flutter/Dart projects.

## Technical Specifications

### 1. Language and Platform Rule Packs
- Create `rules/languages/dart.md`:
  - Sound null safety guidelines (avoiding unvalidated `!` bang operators).
  - Effective Dart idioms (const constructors, immutability, stream controllers disposal).
  - Asynchronous programming best practices (Future/Stream handling, avoiding unawaited futures).
- Create `rules/platforms/flutter.md`:
  - Widget decomposition and performance (minimizing build context rebuilds).
  - State management patterns (Riverpod, Bloc, Provider separation).
  - Platform channels and asset management.
- Register signatures in `alongkit.rules.RULE_SIGNATURES`:
  - `pubspec.yaml` -> `languages/dart.md`, `platforms/flutter.md`
  - `*.dart` -> `languages/dart.md`

### 2. Dependency Scanner (`along_dep_scan.py`)
- Implement `scan_dart_project_deps(project, repo_root, internal_map)`:
  - Parse `pubspec.yaml` (dependencies, dev_dependencies).
  - Parse `pubspec.lock` for exact package versions, repository URLs, and cache paths.
  - Locate pub cache: `$PUB_CACHE` or `~/.pub-cache/hosted/pub.dev/` (and Windows `%LOCALAPPDATA%\Pub\Cache`).
  - Scan dependencies for AI documentation (`AGENTS.md`, `CLAUDE.md`, `README.md`) and package instructions.
  - Handle monorepos / workspaces (`melos.yaml` or path dependencies).

### 3. Lifecycle Runner (`alongkit/lifecycle.py`)
- Add auto-detection for Dart and Flutter projects:
  - Detect Flutter if `pubspec.yaml` contains `sdk: flutter` or `flutter:` section; otherwise Dart.
  - `test`: `flutter test` (or `dart test`)
  - `build`: `flutter build <bundle>` (or `dart compile`)
  - `dev`: `flutter run` (or `dart run`)

## Acceptance Criteria
- [ ] `along rules attach` auto-attaches `dart.md` and `flutter.md` when Dart/Flutter projects are detected.
- [ ] `along dep-scan` parses `pubspec.yaml` / `pubspec.lock` and resolves packages from Pub cache.
- [ ] `along test` and `along build` detect and execute Flutter and Dart lifecycle commands.
- [ ] Comprehensive unit tests for pubspec parsing and cache discovery.
