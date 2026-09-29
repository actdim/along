---
protocol: along
protocol_version: "4.1.0"
slug: empirical-benchmark-harness-and-metrics
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [benchmark, metrics, evaluation, tokens, latency, noise-robustness, arxiv, swe-bench, repobench, intercode]
milestone: v4.8.0-empirical-benchmarking-and-publications
blocked_by: []
related: [docs--arxiv-academic-paper-preprint, docs--engineering-deepdive-medium-devto]
---

# Empirical Benchmark Harness and Comparative Metrics Suite

## Problem

To substantiate academic publication on arXiv and author credible engineering deep-dives on Medium, Dev.to, and Habr, Along requires rigorous quantitative evidence.
Qualitative claims ("Along is lighter, faster, and saves tokens") are insufficient for peer review and skeptical engineers.

Currently, Along lacks an automated diagnostic testbed to systematically compare its execution architecture against baseline agent runtimes:
1. **Append-Only Conversational History** (standard ReAct / LangGraph transcripts).
2. **Rolling Summary Windows** (MemGPT-style periodic summarization).
3. **External Vector RAG** (chunked embeddings with cosine retrieval).
4. **Along Dual-Tier Engine** (Clean-Turn worker loops + Ephemeral Blackboard + Zero-Vector retrieval + Observation distillation).

---

## Evaluation Strategy: Two-Component Design

The benchmark suite consists of two complementary evaluation tracks, providing both external academic validity and controlled diagnostic isolation.

### Track A: External Validity (Public Academic Benchmarks)

Ensures results are directly comparable with published research and eliminates the objection "you only tested on your own toy tasks".

#### A1. SWE-bench Verified Subset (Primary - Software Engineering Tasks)
- **Source**: Princeton SWE-bench (ICLR 2024). Repository: `princeton-nlp/SWE-bench`.
- **Dataset**: SWE-bench Verified (500 curated real issues) or SWE-bench Lite (300 issues).
- **Scope**: Select a representative **25-30 task subset** spanning diverse repositories and difficulty tiers to control LLM API costs.
- **Target Repositories in SWE-bench** (already bundled):
  - `django/django`: Large-scale web framework. Dense module graph, complex middleware chain. Tests multi-file navigation and cross-module dependency tracking.
  - `sympy/sympy`: Symbolic mathematics. Deep recursive structures, metaprogramming. Tests AST awareness and precise symbol search.
  - `pytest-dev/pytest`: Meta-testing framework with plugin architecture. Tests robustness to noisy verbose test outputs (critical for Observation Distillation validation).
  - `scikit-learn/scikit-learn`: ML library. Tests refactoring across tightly-coupled numeric modules.
  - `pallets/flask`: Lightweight web framework. Clean architecture baseline.
- **Execution Setup**:
  - Each task runs inside a Docker container with the exact pre-fix Git state.
  - Fail-to-pass test suite verifies the patch correctness.
  - The same 25-30 tasks are executed under all 4 runtime paradigms.
- **Primary Metric**: `pass@1` (binary success per task, exact match on test suite pass/fail).
- **Cost Estimate**: 25 tasks x 4 paradigms x ~$0.50-2.00 per task = $50-200 per full sweep. Budget for 3 sweeps (different models) = ~$150-600.

#### A2. RepoBench / CrossCodeEval Subset (Retrieval Quality)
- **Source**: RepoBench (ICLR 2024). Repository: `Leolty/repobench`.
- **Purpose**: Isolates and measures the quality of Along's **Zero-Vector Retrieval** (`along-kb-search`) against vector-based RAG baselines.
- **What It Tests**:
  - Cross-file code completion: given a partial function body, find the relevant definition/import from another file in the same repository.
  - Measures whether the retriever locates the correct target class, function, or constant.
- **Retrieval Systems Under Test**:
  1. `AlongZeroVector`: `along-kb-search` with smoothed TF-IDF, word-boundary tokenization, section-anchored snippets (< 150 tokens, < 50 ms).
  2. `ChromaDBBaseline`: Standard chunked embeddings (512 tokens, 50-token overlap) stored in Chroma with `all-MiniLM-L6-v2` encoder.
  3. `BM25Baseline`: Classic BM25 retriever (Lucene-style) for reference.
- **Metrics**:
  - `Recall@1`, `Recall@3`, `Recall@5`: Does the target symbol appear in the top 1/3/5 results?
  - `Retrieved Token Count`: Total tokens returned to the agent prompt (lower is better).
  - `Retrieval Latency (ms)`: Wall-clock time per query.
  - `Installation Footprint`: Dependencies required (Along: 0 native extensions; ChromaDB: hnswlib C++ + onnxruntime; BM25: rank_bm25 pure Python).

#### A3. InterCode CTF Subset (Interactive Terminal Execution)
- **Source**: InterCode (NeurIPS 2023). Repository: `princeton-nlp/intercode`.
- **Purpose**: Tests multi-turn interactive terminal execution with noisy outputs (direct comparability with SKILL.state paper results).
- **Scope**: 30-50 tasks from the Bash/CTF challenge set.
- **Execution**: Docker containers with Linux Bash environments.
- **Metric**: `pass@1` (exact flag match).

### Track B: Controlled Diagnostic Stress Tests (Internal Testbed)

Isolates specific Along architectural claims with deterministic, reproducible scenarios.

#### B1. Long-Horizon Token Scaling (`scripts/benchmarks/horizon_scaling.py`)
- **Purpose**: Prove O(T) cumulative token complexity for Along vs. O(T^2) for append-only runtimes.
- **Setup**:
  - Use a real open-source repository (`psf/requests` or `actdim/along` itself).
  - Define a sequence of N sequential engineering tasks (add test, fix import, rename symbol, update docstring, run linter, fix lint error, etc.).
  - Scale horizons: T in {10, 25, 50, 100} steps.
  - Each step involves: read observation -> reason -> execute action -> receive result.
- **Paradigms Under Test**:
  1. `ReActBaseline`: Appends all observations, reasoning traces, and action results to a growing transcript.
  2. `SummarizationBaseline`: Rolling 3-step conversation window + periodic LLM-generated summary of older steps.
  3. `StatefulBaseline` (LangGraph-style): Injects structured state block alongside full rolling transcript.
  4. `AlongDualTier`: Clean-turn prompt with (Immutable Spec, Structured Blackboard State, Latest Distilled Observation). Intermediate reasoning discarded after validated state patch.
- **Metrics**:
  - Cumulative input tokens at each step t (plotted as scaling curve).
  - Average prompt size per step (characters and tokens).
  - Task accuracy (ratio of correct actions to total actionable events).
- **Statistical Rigor**: 5 random seeds per configuration. Report mean +/- standard deviation. Paired t-test (p < 0.01) at T >= 50.

#### B2. Noise Robustness (Observation Distillation Validation) (`scripts/benchmarks/noise_robustness.py`)
- **Purpose**: Prove that Along's observation distillation filters background telemetry without degrading task accuracy.
- **Setup**:
  - Fix horizon at T=50.
  - Inject background distractor events into subprocess outputs at rates: 0 (clean), 5, 20, 50 events per turn.
  - Distractor categories (modeled after SKILL.state Appendix C):
    - System telemetry logs: `[Syslog] Server-42 CPU load: 88%, RAM usage: 71%`.
    - Deprecation warnings: `DeprecationWarning: use X instead of Y`.
    - Third-party package install chatter: `Collecting package-x==1.2.3...`.
    - CI/CD webhook noise: `[Webhook] Build #1234 queued for branch feature/unrelated`.
- **Metrics**:
  - Task accuracy at each noise level for each runtime paradigm.
  - Prompt size growth under noise (Along should remain flat due to distillation; baselines should grow linearly with noise).

#### B3. State Recovery and External Drift (`scripts/benchmarks/state_recovery.py`)
- **Purpose**: Measure how many turns each runtime needs to recover from silent external changes.
- **Setup**:
  - At step T/2, an external actor silently modifies a target file (simulating a concurrent developer or CI process).
  - The modification contradicts information the agent previously observed and cached in context history.
- **Metrics**:
  - `Recovery Lag`: Number of consecutive turns where the agent acts on stale/incorrect information before adapting.
  - Along target: 0-step recovery (drift detection probe reconciles state immediately).
  - ReAct baseline expected: 5-8 turns of hallucinated repetition (per SKILL.state Experiment 3 findings).

#### B4. Git Concurrency Safety (`scripts/benchmarks/git_concurrency.py`)
- **Purpose**: Verify that Along's file-per-entity architecture and union merge drivers produce zero conflicts under parallel branch execution.
- **Setup**:
  - Spawn 3 simulated agent branches working concurrently on the same Along-enabled repository.
  - Each branch creates issues, updates projections (`.along/ISSUES.md`), and appends session logs.
  - Merge all branches sequentially into main.
- **Metrics**:
  - Git conflict count (Along target: 0).
  - Projection consistency after merge (`along issue sync` produces identical output regardless of merge order).

---

## Requirements

### 1. Harness Infrastructure (`scripts/benchmarks/`)
- Implement unified benchmark runner (`along benchmark run`):
  - `--track A1|A2|A3|B1|B2|B3|B4|all`: Select evaluation track.
  - `--paradigm react|summary|stateful|along|all`: Select runtime paradigm.
  - `--horizon N`: Override step count for Track B tests.
  - `--noise-rate N`: Override noise injection rate for B2.
  - `--seeds N`: Number of random seeds (default: 5).
  - `--model MODEL`: Target LLM (default: gemini-3-flash).
  - `--budget-cap USD`: Hard cost ceiling to abort if API costs exceed budget.

### 2. Runtime Baseline Adapters (`scripts/benchmarks/adapters/`)
- `react_adapter.py`: Appends all observations, thoughts, and actions into a continuous transcript.
- `summarization_adapter.py`: Rolling 3-step window paired with periodic textual summary (triggered every 5 steps).
- `stateful_adapter.py`: Injects structured state JSON alongside full rolling conversational transcript (LangGraph pattern).
- `vector_rag_adapter.py`: ChromaDB with `all-MiniLM-L6-v2` embeddings, 512-token chunks, 50-token overlap.
- `along_adapter.py`: Along Dual-Tier engine with clean-turn prompts, distilled CLI outputs, structured blackboard state, and zero-vector retrieval.
- Each adapter implements a common `RuntimeAdapter` interface: `build_prompt(spec, state, observation) -> str`, `parse_response(raw) -> (action, state_patch)`, `get_token_count() -> int`.

### 3. Measurement Metrics Engine (`scripts/benchmarks/metrics.py`)
- Automatically measure and record per-step and per-episode:
  - **Cumulative Token Consumption**: Total input and output tokens consumed across the full horizon.
  - **Prompt Footprint**: Average and peak prompt character length per step.
  - **Step Execution Latency**: Wall-clock duration per turn (ms).
  - **Task Accuracy / pass@1**: Success rate measured by test suite or ground-truth event matching.
  - **Noise Robustness Score**: Task accuracy under distractor injection at calibrated rates.
  - **State Recovery Lag**: Consecutive incorrect turns after external drift event.
  - **Retrieval Precision**: Recall@1, Recall@3, Retrieved Token Count (Track A2 only).
  - **Git Conflict Count**: Merge conflict tally (Track B4 only).

### 4. Automated Export and Plotting (`scripts/benchmarks/export.py`)
- Export results to:
  - Machine-readable JSON and CSV (`benchmarks/results/<track>/<date>/`).
  - Formatted LaTeX tables ready for direct inclusion in the arXiv paper (`benchmarks/latex/`).
  - Markdown comparison tables for web articles (`benchmarks/markdown/`).
  - SVG scaling curve plots via `matplotlib` (`benchmarks/figures/`):
    - Token scaling curves (T vs. cumulative tokens, one line per paradigm).
    - Noise robustness bar charts (accuracy vs. noise rate per paradigm).
    - Retrieval precision scatter plots (Recall vs. latency vs. token footprint).

---

## Execution Plan (Phased)

### Phase 1: Infrastructure (Week 1-2)
- [ ] Scaffold `scripts/benchmarks/` package with harness runner, adapter interface, and metrics engine.
- [ ] Implement `ReActBaseline` and `AlongDualTier` adapters (minimum viable pair).
- [ ] Build Track B1 (Horizon Scaling) on `psf/requests` with T in {10, 25, 50}.

### Phase 2: Controlled Tests (Week 3-4)
- [ ] Implement `SummarizationBaseline` and `StatefulBaseline` adapters.
- [ ] Build Track B2 (Noise Robustness) with distractor injection framework.
- [ ] Build Track B3 (State Recovery) with external drift simulation.
- [ ] Build Track B4 (Git Concurrency) with parallel branch spawner.
- [ ] Run full Track B sweep on Gemini-3-Flash: 4 paradigms x 4 horizons x 5 seeds.

### Phase 3: Public Benchmarks (Week 5-6)
- [ ] Integrate SWE-bench Verified Docker harness (Track A1, 25-task subset).
- [ ] Integrate RepoBench evaluation script (Track A2, retrieval quality).
- [ ] Integrate InterCode CTF Docker harness (Track A3, 30-task subset).
- [ ] Run full Track A sweep: 4 paradigms x 3 benchmarks x target model.

### Phase 4: Export and Publication Assets (Week 7)
- [ ] Generate LaTeX tables, SVG plots, and Markdown summaries.
- [ ] Review statistical significance (paired t-test, p < 0.01 at T >= 50).
- [ ] Archive raw results in `benchmarks/results/` with full reproducibility metadata (model, temperature, seeds, commit SHA).

## Acceptance Criteria

- [ ] Automated benchmark harness executable via `python scripts/along_benchmark.py` or `along benchmark run`.
- [ ] Supports all 4 runtime paradigms across all evaluation tracks (A1-A3, B1-B4).
- [ ] Generates publication-ready metrics: cumulative tokens, latency, noise robustness, state recovery lag, retrieval quality.
- [ ] Results include statistical significance tests with 5 seeds and paired t-test.
- [ ] Clean ASCII formatting with zero forbidden typography characters.
