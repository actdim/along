#!/usr/bin/env python3
"""
alongkit.kb - Knowledge Base synthesis contracts, deterministic cross-linking, and AST grounding.

This module consolidates LLM-Wiki Knowledge Base mechanisms:
1. TopicDictionary: in-memory lookup table of topic titles, slugs, and tags from docs/topic--*.md.
2. Cross-Link Engine: scan_crosslinks() and apply_crosslinks() with CommonMark code fence tracking,
   link masking, heading exclusions, and first-occurrence-per-section bounding.
3. Section Taxonomy Contracts: SECTION_CONTRACTS and validate_topic_sections() for standard topic types
   (architecture, domain-model, setup-workflow).
4. AST Code Symbol Extractor: extract_code_symbols() across codebase Python files.
5. Symbol Grounding Verifier: verify_grounded_symbols() to flag ghost symbols in documentation.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_kb_sync.py)"
    )

import ast
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from alongkit import frontmatter, markdown, repo, textio

STANDARD_ARTICLES = [
    ("topic--architecture.md", "System Architecture & Flow", "architecture", ["architecture", "boundaries", "providers", "mcp", "dashboard"]),
    ("topic--domain-model.md", "Domain Model & Entity Ecosystem", "domain-model", ["domain-model", "entities", "schemas", "dag", "metadata"]),
    ("topic--setup-and-workflow.md", "Setup, Installation & Agent Workflows", "setup-workflow", ["setup", "workflow", "installation", "lifecycle", "quality-gates"]),
]

LEGACY_FILE_MAPPING = {
    "01-architecture.md": "topic--architecture.md",
    "02-domain-model.md": "topic--domain-model.md",
    "03-setup-and-workflow.md": "topic--setup-and-workflow.md",
    "04-frontend-frameworks.md": "topic--frontend-frameworks.md",
    "dependencies.md": "topic--dependencies.md",
    "MIGRATIONS.md": "topic--migrations.md",
}

SECTION_CONTRACTS: Dict[str, List[Dict[str, Any]]] = {
    "architecture": [
        {
            "canonical_name": "System Topology & Overview",
            "patterns": [r"topology", r"architecture", r"overview", r"boundaries"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Core Components & Engine Implementation",
            "patterns": [r"core\s+components", r"components", r"subsystems", r"engine\s+implementation", r"modules"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Data Flow & Execution Workflow",
            "patterns": [r"data\s+flow", r"workflow", r"execution\s+flow", r"flow", r"lifecycle"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Invariants & Failure Modes",
            "patterns": [r"invariants", r"failure\s+modes", r"concurrency", r"security", r"rationale", r"incident", r"error\s+handling"],
            "min_lines": 2,
        },
    ],
    "domain-model": [
        {
            "canonical_name": "Entity Taxonomy & Ecosystem",
            "patterns": [r"entity\s+taxonomy", r"taxonomy", r"ecosystem", r"entity\s+types"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Front-matter Schemas & Metadata",
            "patterns": [r"front-matter\s+schemas", r"frontmatter", r"schemas", r"metadata"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Graph Invariance & Relationships",
            "patterns": [r"graph\s+relationships", r"graph\s+invariance", r"relationships", r"linking", r"dag"],
            "min_lines": 2,
        },
    ],
    "setup-workflow": [
        {
            "canonical_name": "Prerequisites & Installation",
            "patterns": [r"prerequisites", r"installation", r"requirements", r"setup", r"runtime"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Runner Commands & Lifecycle Scripts",
            "patterns": [r"runner\s+commands", r"commands", r"scripts", r"lifecycle\s+runners", r"workflow"],
            "min_lines": 2,
        },
        {
            "canonical_name": "Quality Gates & Verification",
            "patterns": [r"quality\s+gates?", r"gates?", r"verification", r"tests?", r"hermetic"],
            "min_lines": 2,
        },
    ],
}


@dataclass
class SectionViolation:
    file: str
    topic_type: str
    section: str
    error: str


def validate_topic_sections(doc_path: str, text: str, topic_type: str) -> List[SectionViolation]:
    """Verifies that mandatory structural headings for standard topic types exist and contain content."""
    contracts = SECTION_CONTRACTS.get(topic_type)
    if not contracts:
        return []

    fence = markdown.FenceTracker()
    lines = text.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_heading: Optional[str] = None
    current_body: List[str] = []

    for line in lines:
        if fence.process_line(line) or fence.in_fence:
            if current_heading is not None:
                current_body.append(line)
            continue

        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_body))
            raw_h = stripped[3:].strip()
            clean_h = re.sub(r"^\d+[\.\)]\s*", "", raw_h).strip()
            current_heading = clean_h
            current_body = []
        elif current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_body))

    violations: List[SectionViolation] = []
    for contract in contracts:
        matched = False
        matched_body: List[str] = []
        for h_text, body in sections:
            for pat in contract["patterns"]:
                if re.search(pat, h_text, re.IGNORECASE):
                    matched = True
                    matched_body = body
                    break
            if matched:
                break

        if not matched:
            violations.append(SectionViolation(
                file=doc_path,
                topic_type=topic_type,
                section=contract["canonical_name"],
                error=f"missing required section (expected heading matching: {contract['patterns'][0]})",
            ))
        else:
            substantive_lines = [
                l.strip() for l in matched_body
                if l.strip() and not l.strip().startswith("<!--")
            ]
            if len(substantive_lines) < contract["min_lines"]:
                violations.append(SectionViolation(
                    file=doc_path,
                    topic_type=topic_type,
                    section=contract["canonical_name"],
                    error="empty section content (insufficient substantive lines)",
                ))

    return violations


@dataclass
class TopicEntry:
    filename: str
    slug: str
    title: str
    tags: List[str]
    topic_type: str

    @property
    def target(self) -> str:
        return self.filename


GENERIC_TERMS_STOPLIST: Set[str] = {
    "and", "for", "the", "with", "open", "type", "rule", "gate",
    "data", "flow", "test", "docs", "kb", "map", "file", "code",
    "repo", "root", "link", "node", "core", "tool", "along",
    "setup", "view", "show", "step", "user", "mode", "task",
    "spec", "part", "work", "read", "fast", "path", "done",
}


class TopicDictionary:
    """In-memory dictionary of topic titles, slugs, and tags for cross-linking."""

    def __init__(self) -> None:
        self.entries: Dict[str, TopicEntry] = {}
        self.term_to_target: Dict[str, str] = {}
        self.sorted_terms: List[Tuple[str, str]] = []

    def add_entry(
        self,
        entry_or_term: Union[TopicEntry, str],
        target: Optional[str] = None,
        slug: Optional[str] = None,
    ) -> None:
        if isinstance(entry_or_term, TopicEntry):
            entry = entry_or_term
        else:
            term = entry_or_term
            tgt = target or f"{term}.md"
            slg = slug or term
            entry = TopicEntry(
                filename=tgt,
                slug=slg,
                title=term,
                tags=[],
                topic_type="topic",
            )

        self.entries[entry.slug] = entry
        tgt_fn = entry.filename[2:] if entry.filename.startswith("./") else entry.filename
        if not isinstance(entry_or_term, TopicEntry) and target:
            # If explicit term and target supplied, directly register
            self._register_term(entry.title, tgt_fn)

        if entry.title and len(entry.title.strip()) >= 3:
            clean_title = entry.title.strip()
            self._register_term(clean_title, tgt_fn)

        clean_slug = entry.slug.replace("topic--", "")
        if len(clean_slug) >= 3 and clean_slug.lower() not in GENERIC_TERMS_STOPLIST:
            self._register_term(clean_slug, tgt_fn)
            if "-" in clean_slug:
                self._register_term(clean_slug.replace("-", " "), tgt_fn)

        for tag in entry.tags:
            tag_clean = tag.strip().lower()
            if len(tag_clean) >= 4 and tag_clean not in GENERIC_TERMS_STOPLIST:
                self._register_term(tag_clean, tgt_fn)
                if "-" in tag_clean:
                    self._register_term(tag_clean.replace("-", " "), tgt_fn)

        self._rebuild_sorted_terms()

    def get_entries_for_slug(self, slug: str) -> List[TopicEntry]:
        norm = slug.replace("topic--", "")
        return [e for e in self.entries.values() if e.slug != slug and e.slug != norm]

    @classmethod
    def build_from_articles(cls, articles: List[Dict[str, Any]]) -> "TopicDictionary":
        d = cls()
        for art in articles:
            d.add_entry(TopicEntry(
                filename=art.get("filename", ""),
                slug=art.get("slug", ""),
                title=art.get("title", ""),
                tags=art.get("tags") or [],
                topic_type=art.get("type", "topic"),
            ))
        return d

    def _register_term(self, term: str, target: str) -> None:
        norm = term.strip().lower()
        if norm and norm not in GENERIC_TERMS_STOPLIST:
            self.term_to_target[norm] = target

    def _rebuild_sorted_terms(self) -> None:
        self.sorted_terms = sorted(
            self.term_to_target.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

    @classmethod
    def build_from_dir(cls, docs_dir: str) -> "TopicDictionary":
        d = cls()
        if not os.path.isdir(docs_dir):
            return d
        for fname in sorted(os.listdir(docs_dir)):
            if not fname.endswith(".md") or fname == "INDEX.md":
                continue
            fpath = os.path.join(docs_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                content = textio.read_text(fpath)
                fm, body = frontmatter.parse_tolerant(content, path=fpath)
                slug = fm.get("slug") or fname.replace(".md", "")
                title = fm.get("title")
                if not title:
                    h1_m = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
                    title = h1_m.group(1).strip() if h1_m else slug.replace("topic--", "").replace("-", " ").title()
                entry = TopicEntry(
                    filename=fname,
                    slug=slug.replace("topic--", ""),
                    title=title,
                    tags=fm.get("tags") or [],
                    topic_type=fm.get("type", "topic"),
                )
                d.add_entry(entry)
            except (OSError, UnicodeDecodeError, ValueError, frontmatter.FrontmatterError):
                continue
        return d


@dataclass
class CrossLinkCandidate:
    file: str
    line: int
    term: str
    target: str
    section: str


def _mask_markdown_structures(line: str) -> str:
    """Replaces links, images, and inline code with spaces preserving character offsets."""
    res = re.sub(r"\[([^\]]*)\]\([^)]*\)", lambda m: " " * len(m.group(0)), line)
    res = re.sub(r"`+[^`]+`+", lambda m: " " * len(m.group(0)), res)
    return res


def scan_crosslinks(
    doc_path: str,
    text: Union[str, TopicDictionary],
    topic_dict: Optional[TopicDictionary] = None,
    current_slug: Optional[str] = None,
) -> List[CrossLinkCandidate]:
    """Audits text and returns candidate unlinked topic mentions outside code fences/links."""
    if isinstance(text, TopicDictionary):
        topic_dict = text
        text = doc_path
        doc_path = "document.md"
    if topic_dict is None:
        return []

    candidates: List[CrossLinkCandidate] = []
    fence = markdown.FenceTracker()
    lines = text.splitlines()

    current_section = "Preamble"
    current_target = f"topic--{current_slug}.md" if current_slug else None
    if current_target and not current_target.startswith("topic--"):
        current_target = f"topic--{current_target}"

    linked_in_section: Set[str] = set()

    for line_idx, line in enumerate(lines, 1):
        if fence.process_line(line) or fence.in_fence:
            continue

        stripped = line.strip()
        if stripped.startswith("## "):
            raw_h = stripped[3:].strip()
            current_section = re.sub(r"^\d+[\.\)]\s*", "", raw_h).strip()
            linked_in_section.clear()
            continue

        if stripped.startswith("#"):
            continue

        # Register any targets already linked on this line in the section
        for lm in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", line):
            href = lm.group(1).split("#")[0].strip()
            if href and not href.startswith(("http://", "https://", "#", "file://")):
                t_base = os.path.basename(href)
                linked_in_section.add(t_base)
                linked_in_section.add(href)
                linked_in_section.add(f"./{t_base}")

        clean_line = _mask_markdown_structures(line)

        for term, target in topic_dict.sorted_terms:
            target_clean = target[2:] if target.startswith("./") else target
            if (
                target == current_target
                or target_clean == current_target
                or target in linked_in_section
                or target_clean in linked_in_section
                or f"./{target_clean}" in linked_in_section
            ):
                continue
            pat = re.compile(r"\b(" + re.escape(term) + r")\b", re.IGNORECASE)
            m = pat.search(clean_line)
            if m:
                candidates.append(CrossLinkCandidate(
                    file=doc_path,
                    line=line_idx,
                    term=m.group(1),
                    target=f"./{target_clean}",
                    section=current_section,
                ))
                linked_in_section.add(target)
                linked_in_section.add(target_clean)
                linked_in_section.add(f"./{target_clean}")

    return candidates


def _replace_unlinked_terms(
    line: str,
    sorted_terms: List[Tuple[str, str]],
    current_target: Optional[str],
    linked_in_section: Set[str],
) -> Tuple[str, int]:
    """Replaces unlinked terms on a single line, masking links and code spans first."""
    # Register existing links on this line
    for lm in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", line):
        href = lm.group(1).split("#")[0].strip()
        if href and not href.startswith(("http://", "https://", "#", "file://")):
            t_base = os.path.basename(href)
            linked_in_section.add(t_base)
            linked_in_section.add(href)
            linked_in_section.add(f"./{t_base}")

    placeholders: List[str] = []

    def _save_span(m: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(m.group(0))
        return f"\x00M{idx}\x00"

    masked = re.sub(r"!?\[[^\]]*\]\([^)]*\)", _save_span, line)
    masked = re.sub(r"`+[^`]+`+", _save_span, masked)

    applied_count = 0
    for term, target in sorted_terms:
        target_clean = target[2:] if target.startswith("./") else target
        if (
            target == current_target
            or target_clean == current_target
            or target in linked_in_section
            or target_clean in linked_in_section
            or f"./{target_clean}" in linked_in_section
        ):
            continue

        pattern = re.compile(r"\b(" + re.escape(term) + r")\b", re.IGNORECASE)
        m = pattern.search(masked)
        if m:
            matched_str = m.group(1)
            rel_link = f"[{matched_str}](./{target_clean})"
            masked = masked[:m.start()] + rel_link + masked[m.end():]
            linked_in_section.add(target)
            linked_in_section.add(target_clean)
            linked_in_section.add(f"./{target_clean}")
            applied_count += 1

    for idx in range(len(placeholders) - 1, -1, -1):
        masked = masked.replace(f"\x00M{idx}\x00", placeholders[idx])

    return masked, applied_count


def apply_crosslinks(
    doc_path: str,
    text: Union[str, TopicDictionary],
    topic_dict: Optional[TopicDictionary] = None,
    current_slug: Optional[str] = None,
) -> Tuple[str, int]:
    """Deterministically inserts relative cross-links for the first occurrence of a concept per section."""
    if isinstance(text, TopicDictionary):
        topic_dict = text
        text = doc_path
        doc_path = "document.md"
    if topic_dict is None:
        return text, 0

    fence = markdown.FenceTracker()
    lines = text.splitlines()
    output_lines: List[str] = []
    total_applied = 0

    current_target = f"topic--{current_slug}.md" if current_slug else None
    if current_target and not current_target.startswith("topic--"):
        current_target = f"topic--{current_target}"

    linked_in_section: Set[str] = set()

    for line in lines:
        if fence.process_line(line) or fence.in_fence:
            output_lines.append(line)
            continue

        stripped = line.strip()
        if stripped.startswith("## "):
            linked_in_section.clear()
            output_lines.append(line)
            continue

        if stripped.startswith("#"):
            output_lines.append(line)
            continue

        new_line, applied = _replace_unlinked_terms(
            line, topic_dict.sorted_terms, current_target, linked_in_section
        )
        total_applied += applied
        output_lines.append(new_line)

    newline = "\r\n" if "\r\n" in text else "\n"
    return newline.join(output_lines) + (newline if text.endswith(("\n", "\r\n")) else ""), total_applied


@dataclass
class CodeSymbol:
    name: str
    kind: str
    file: str
    line: int


class SymbolInventory:
    def __init__(self) -> None:
        self.symbols: Dict[str, List[CodeSymbol]] = {}
        self.names: Set[str] = set()

    def add(self, sym: CodeSymbol) -> None:
        self.names.add(sym.name)
        if sym.name not in self.symbols:
            self.symbols[sym.name] = []
        self.symbols[sym.name].append(sym)

    def __contains__(self, name: str) -> bool:
        return name in self.names


def extract_code_symbols(repo_root: str) -> SymbolInventory:
    """Extracts code symbols (classes, functions, constants, commands) from repository code files."""
    inventory = SymbolInventory()
    repo_root = os.path.abspath(repo_root)

    target_subdirs = ["scripts", "dashboard", "tests"]
    along_scripts = os.path.join(repo_root, ".along", "scripts")
    if os.path.isdir(along_scripts):
        target_subdirs.append(os.path.join(".along", "scripts"))

    for subdir in target_subdirs:
        scan_dir = os.path.join(repo_root, subdir)
        if not os.path.isdir(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in repo.IGNORED_DIRS and d not in repo.PROVIDER_DIRS]
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = os.path.join(root, f)
                rel_fpath = repo.safe_relpath(fpath, repo_root).replace("\\", "/")
                try:
                    source = textio.read_text(fpath)
                    tree = ast.parse(source, filename=rel_fpath)
                except (OSError, UnicodeDecodeError, SyntaxError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        inventory.add(CodeSymbol(name=node.name, kind="class", file=rel_fpath, line=node.lineno))
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                inventory.add(CodeSymbol(
                                    name=f"{node.name}.{item.name}",
                                    kind="method",
                                    file=rel_fpath,
                                    line=item.lineno,
                                ))
                                inventory.add(CodeSymbol(
                                    name=item.name,
                                    kind="method",
                                    file=rel_fpath,
                                    line=item.lineno,
                                ))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        inventory.add(CodeSymbol(name=node.name, kind="function", file=rel_fpath, line=node.lineno))
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 2:
                                inventory.add(CodeSymbol(name=target.id, kind="constant", file=rel_fpath, line=node.lineno))
                    elif isinstance(node, ast.AnnAssign):
                        if isinstance(node.target, ast.Name) and node.target.id.isupper() and len(node.target.id) > 2:
                            inventory.add(CodeSymbol(name=node.target.id, kind="constant", file=rel_fpath, line=node.lineno))

    try:
        from along_exec import TOOL_MAPPINGS
        for cmd in TOOL_MAPPINGS.keys():
            inventory.add(CodeSymbol(name=cmd, kind="command", file="scripts/along_exec.py", line=46))
            inventory.add(CodeSymbol(name=f"along {cmd}", kind="command", file="scripts/along_exec.py", line=46))
    except (ImportError, AttributeError):
        pass

    return inventory


EXTERNAL_SYMBOL_ALLOWLIST: Set[str] = {
    "FastAPI", "BaseModel", "Field", "APIRouter", "WebSocket", "Request",
    "Response", "HTTPException", "Depends", "Query", "Header",
    "Cytoscape", "Uvicorn", "Hatchling", "Pytest", "UnitTestCase",
    "Pydantic", "ruamel.yaml", "YAML", "Path", "Dict", "List", "Set",
    "Tuple", "Optional", "Any", "Union", "Callable", "NamedTuple",
    "Enum", "dataclass", "Iterator", "Iterable", "Generator",
    # Standard library modules & attributes
    "sys", "os", "re", "shutil", "json", "subprocess", "tempfile", "unittest",
    "argparse", "hashlib", "datetime", "time", "pathlib", "typing", "math", "io", "ast",
    "sys.path", "sys.executable", "os.remove", "os.path", "os.environ",
    # Win32 platform symbols
    "ReplaceFileW",
    # MCP code-review-graph tools
    "get_impact_radius_tool", "get_affected_flows_tool", "query_graph_tool",
    "build_or_update_graph_tool", "get_review_context_tool", "semantic_search_nodes_tool",
    # Entity frontmatter fields
    "blocked_by", "duplicate_of", "superseded_by", "related", "issues_advanced",
    "issues_completed", "progress_pct", "target_issues",
    # Frontend Dynstruct framework symbols
    "ComponentStruct", "DashboardApiClient", "KeysOf", "ToMsgChannelPrefix",
    "ToMsgStruct", "MsgStruct", "window.__ALONG_DATA__",
}

PYTHON_BUILTINS_AND_KEYWORDS: Set[str] = {
    "dir", "id", "len", "open", "str", "int", "float", "bool", "dict", "list",
    "set", "tuple", "print", "super", "type", "range", "zip", "map", "filter",
    "all", "any", "isinstance", "issubclass", "getattr", "setattr", "hasattr",
    "repr", "iter", "next", "hash", "sum", "min", "max", "round", "abs",
    "def", "class", "import", "from", "return", "for", "in", "is", "not",
    "and", "or", "True", "False", "None", "async", "await", "with", "as",
    "try", "except", "finally", "raise", "pass", "break", "continue", "yield",
    "global", "nonlocal", "lambda",
}

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*_[a-z0-9_]+$")
_PASCAL_CASE_RE = re.compile(r"^[A-Z][a-z0-9]+[A-Z][a-zA-Z0-9]*$")
_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+$")
_DOTTED_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]+$")
_CALL_SYNTAX_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\(\)$")


@dataclass
class GhostSymbol:
    file: str
    line: int
    symbol: str
    reason: str


def verify_grounded_symbols(
    doc_path: str,
    text: str,
    symbol_inventory: Union[SymbolInventory, Set[str], Collection[str]],
) -> List[GhostSymbol]:
    """Verifies that code symbols documented in backticks physically resolve in repository AST."""
    ghosts: List[GhostSymbol] = []
    fence = markdown.FenceTracker()
    lines = text.splitlines()

    inv_names = (
        symbol_inventory.names
        if isinstance(symbol_inventory, SymbolInventory)
        else set(symbol_inventory)
    )

    backtick_re = re.compile(r"`([^`\n]+)`")

    for line_idx, line in enumerate(lines, 1):
        if fence.process_line(line) or fence.in_fence:
            continue

        for m in backtick_re.finditer(line):
            raw_cand = m.group(1).strip()
            if not raw_cand or " " in raw_cand or "\t" in raw_cand:
                continue
            if "/" in raw_cand or "\\" in raw_cand:
                continue
            if raw_cand.startswith(("-", "--", "/")):
                continue
            if any(raw_cand.endswith(ext) for ext in (
                ".py", ".md", ".json", ".toml", ".txt", ".ts", ".sh",
                ".bat", ".ps1", ".yaml", ".yml", ".html", ".css", ".js",
                ".mod", ".lock", ".cfg", ".ini", ".env", ".cmd"
            )):
                continue
            if raw_cand == "node_modules":
                continue
            if any(c in raw_cand for c in (":", "=", "<", ">", "{", "}", "*", "[", "]", "@")):
                continue

            cand = raw_cand
            call_m = _CALL_SYNTAX_RE.match(cand)
            if call_m:
                cand = call_m.group(1)

            if cand in PYTHON_BUILTINS_AND_KEYWORDS or cand in EXTERNAL_SYMBOL_ALLOWLIST:
                continue

            # Skip JS / object property accesses like c.model, c.msgBus, window.*
            if cand.startswith(("c.", "self.", "window.")):
                continue

            # Skip alongkit submodules like alongkit.bootstrap, alongkit.lifecycle
            if cand.startswith("alongkit."):
                continue

            is_symbol_signature = (
                _SNAKE_CASE_RE.match(cand) or
                _PASCAL_CASE_RE.match(cand) or
                _UPPER_SNAKE_RE.match(cand) or
                _DOTTED_IDENT_RE.match(cand)
            )
            if not is_symbol_signature:
                continue

            found = False
            if cand in inv_names:
                found = True
            elif "." in cand:
                parts = cand.split(".")
                rightmost = parts[-1]
                if rightmost in inv_names or rightmost in EXTERNAL_SYMBOL_ALLOWLIST:
                    found = True

            if not found:
                ghosts.append(GhostSymbol(
                    file=doc_path,
                    line=line_idx,
                    symbol=raw_cand,
                    reason=f"symbol '{cand}' does not resolve to any class, function, method, or constant in codebase AST",
                ))

    return ghosts
