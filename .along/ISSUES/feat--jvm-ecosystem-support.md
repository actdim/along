---
protocol: along
protocol_version: "4.1.0"
slug: jvm-ecosystem-support
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [java, kotlin, jvm, maven, gradle, rules, dep-scan, lifecycle]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Java & Kotlin (JVM) Ecosystem Support (Rules, Dep-Scan & Lifecycle)

## Goal
Implement end-to-end Along protocol support for the JVM ecosystem, including Java and Kotlin engineering rules, Maven and Gradle dependency and submodule scanning, and automated lifecycle hook detection.

## Problem Statement
Java and Kotlin are dominant backends in enterprise monorepos and Android/KMP development. Currently, Along lacks language-specific rule packs for Java/Kotlin, `along-dep-scan` cannot discover Maven (`pom.xml`) or Gradle (`build.gradle`, `build.gradle.kts`, `gradle/libs.versions.toml`) dependencies, and `along test`/`along build` does not auto-detect `gradlew` or `mvnw` wrappers.

## Technical Specifications

### 1. Language Rule Packs
- Create `rules/languages/java.md`:
  - Modern Java conventions (Java 17/21+, records, sealed types, pattern matching, virtual threads).
  - Spring Boot and Quarkus framework patterns.
  - JUnit 5 / AssertJ test standards.
- Create `rules/languages/kotlin.md`:
  - Idiomatic Kotlin (coroutines, structured concurrency, Flow, immutability, data classes).
  - Kotlin Multiplatform (KMP) source set layout conventions.
- Register detection signatures in `alongkit.rules.RULE_SIGNATURES`:
  - `pom.xml` -> `languages/java.md`
  - `build.gradle` -> `languages/java.md`
  - `build.gradle.kts` -> `languages/kotlin.md`
  - `*.kt` / `*.kts` -> `languages/kotlin.md`
  - `*.java` -> `languages/java.md`

### 2. Dependency & Submodule Scanner (`along_dep_scan.py`)
- Implement `scan_jvm_project_deps(project, repo_root, internal_map)`:
  - Parse Maven `pom.xml` dependencies (`<dependency><groupId>...</groupId><artifactId>...</artifactId><version>...</version></dependency>`).
  - Parse Gradle `build.gradle` and `build.gradle.kts` dependency blocks.
  - Parse Gradle Version Catalogs (`gradle/libs.versions.toml`).
  - Inspect local caches: Maven repository (`~/.m2/repository`) and Gradle cache (`~/.gradle/caches/modules-2/files-2.1`).
  - Map internal multi-module Gradle/Maven subprojects into internal monorepo DAG.

### 3. Lifecycle Runner (`alongkit/lifecycle.py`)
- Add auto-detection for Gradle projects (`build.gradle`, `build.gradle.kts`, `settings.gradle`):
  - `build`: `./gradlew build` (Windows: `gradlew.bat build`)
  - `test`: `./gradlew test -q` (Windows: `gradlew.bat test -q`)
  - `dev`: `./gradlew bootRun` / `./gradlew run`
- Add auto-detection for Maven projects (`pom.xml`):
  - `build`: `./mvnw package -DskipTests` (Windows: `mvnw.cmd package -DskipTests`)
  - `test`: `./mvnw test -q` (Windows: `mvnw.cmd test -q`)
  - `dev`: `./mvnw spring-boot:run`

## Acceptance Criteria
- [ ] `along rules attach` auto-attaches `java.md` and `kotlin.md` when project carries JVM files.
- [ ] `along dep-scan` discovers Maven and Gradle dependencies and records them in `topic--dependencies.md`.
- [ ] `along test` and `along build` auto-synthesize verified Gradle/Maven hooks.
- [ ] Hermetic tests verify JVM manifest discovery and wrapper resolution.
