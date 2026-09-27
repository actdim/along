---
protocol: along
protocol_version: "4.1.0"
slug: cpp-ecosystem-support
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [cpp, c, cmake, vcpkg, conan, native, rules, dep-scan, lifecycle]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# C and C++ Ecosystem Support (Rules, Manifests & Lifecycle)

## Goal
Implement Along protocol support for modern C and C++ projects, providing engineering guidelines (C++20, RAII, memory safety, sanitizers), build system manifest parsing (CMake, vcpkg, Conan), and lifecycle hook orchestration.

## Problem Statement
C and C++ remain critical for high-performance systems, game engines, embedded devices, and core platform runtimes. C/C++ lacks a single standardized package manager, relying instead on CMake, vcpkg, and Conan. Along currently has no rules for C/C++ safety practices, does not inspect native package manifests, and lacks automated lifecycle runners for CMake or CTest.

## Technical Specifications

### 1. Language Rule Pack
- Create `rules/languages/cpp.md`:
  - Modern C++ guidelines (C++20 features, concepts, ranges, `std::span`, `std::string_view`).
  - Resource management (strict RAII, smart pointers `std::unique_ptr`/`std::shared_ptr`, avoiding naked `new`/`delete`).
  - Memory safety and verification (enabling ASan, UBSan, TSan; compile flags `-Wall -Wextra -Wpedantic`).
  - Modular header organization (header guards, `#pragma once`, modules where supported).
- Register signatures in `alongkit.rules.RULE_SIGNATURES`:
  - `CMakeLists.txt` -> `languages/cpp.md`
  - `vcpkg.json` -> `languages/cpp.md`
  - `conanfile.py`, `conanfile.txt` -> `languages/cpp.md`
  - `*.cpp`, `*.cc`, `*.cxx`, `*.hpp`, `*.h` -> `languages/cpp.md`

### 2. Dependency & Manifest Scanner (`along_dep_scan.py`)
- Implement `scan_cpp_project_deps(project, repo_root, internal_map)`:
  - Detect project type via `CMakeLists.txt`, `vcpkg.json`, `conanfile.txt`, `conanfile.py`.
  - Parse `vcpkg.json` for declared dependencies and version constraints.
  - Parse `conanfile.txt` / `conanfile.py` requirements.
  - Inspect vcpkg installed directories (`vcpkg_installed/` or `$VCPKG_ROOT/installed`).
  - Inspect Conan cache (`~/.conan2/p/` or `~/.conan/data/`).
  - Extract AI guidance and include documentation from resolved package directories.

### 3. Lifecycle Runner (`alongkit/lifecycle.py`)
- Add auto-detection for C/C++ projects:
  - If `CMakeLists.txt` exists:
    - `build`: `cmake --build build` (with fallback to `cmake -B build` if build directory missing)
    - `test`: `ctest --test-dir build --output-on-failure`
  - If `Makefile` exists without CMake:
    - `build`: `make`
    - `test`: `make test` or `make check`

## Acceptance Criteria
- [ ] `along rules attach` attaches `cpp.md` for CMake, vcpkg, Conan, and C/C++ source trees.
- [ ] `along dep-scan` identifies vcpkg and Conan dependencies and records them in dependency projections.
- [ ] `along test` and `along build` detect CMake / CTest projects and configure verified hooks.
- [ ] Unit tests for manifest detection and parsing.
