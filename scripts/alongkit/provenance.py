from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along kb-sync --help"
    )

import hashlib
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import frontmatter, proc, repo, textio


def compute_content_hash(text: str) -> str:
    """Deterministic SHA-256 hash of text normalized to LF line endings."""
    normalized = text.replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_all_topic_files(repo_root: str) -> List[Tuple[str, str]]:
    """List of (context_dir, topic_rel_to_repo) for all topic articles across repo and subprojects."""
    contexts = [repo_root] + repo.find_agent_contexts(repo_root)
    seen = set()
    topics: List[Tuple[str, str]] = []
    for ctx in contexts:
        docs_dir = os.path.join(ctx, "docs")
        if not os.path.isdir(docs_dir):
            continue
        try:
            entries = sorted(os.listdir(docs_dir))
        except OSError:
            continue
        for name in entries:
            if not name.endswith(".md") or name == "INDEX.md":
                continue
            if name.startswith("topic--along-protocol"):
                continue
            full_path = os.path.join(docs_dir, name)
            if not os.path.isfile(full_path):
                continue
            rel_topic = repo.canonical_relpath(full_path, repo_root)
            if rel_topic not in seen:
                seen.add(rel_topic)
                topics.append((ctx, rel_topic))
    return topics


def topic_sources(
    repo_root: str,
    read: Optional[Callable[[str], Optional[str]]] = None,
) -> Dict[str, List[Tuple[str, Optional[str]]]]:
    """Parses docs/topic--*.md front-matter.

    Returns:
        {source_path: [(topic_path, recorded_hash), ...]}
    where source_path and topic_path are canonical paths relative to repo_root.
    Dict entries with a hash are tracked; plain strings or entries without a hash
    have recorded_hash = None (untracked).
    """
    mapping: Dict[str, List[Tuple[str, Optional[str]]]] = {}
    for ctx, topic_rel in find_all_topic_files(repo_root):
        content = read(topic_rel) if read else None
        if content is None and not read:
            full_path = os.path.join(repo_root, topic_rel)
            if os.path.isfile(full_path):
                content = textio.read_text(full_path, strict=False)
        if not content:
            continue

        try:
            fm, _ = frontmatter.parse(content, path=topic_rel)
        except (frontmatter.FrontmatterError, OSError, ValueError):
            continue

        sources = fm.get("sources")
        if not sources or not isinstance(sources, list):
            continue

        for item in sources:
            rec_hash: Optional[str] = None
            if isinstance(item, dict):
                src_path = item.get("path")
                rec_hash = item.get("hash")
            elif isinstance(item, str):
                src_path = item
            else:
                continue

            if not src_path:
                continue

            # Resolve source path against the context directory that owns this docs/
            src_full = os.path.normpath(os.path.join(ctx, src_path))
            src_rel = repo.canonical_relpath(src_full, repo_root)

            mapping.setdefault(src_rel, []).append((topic_rel, rec_hash))

    return mapping


def drift_for(
    repo_root: str,
    paths: Iterable[str],
    read: Optional[Callable[[str], Optional[str]]] = None,
) -> List[Tuple[str, str, Optional[str], Optional[str]]]:
    """Check changed paths for provenance drift against tracked topic sources.

    Returns:
        [(topic_rel, source_rel, recorded_hash, actual_hash)]
    for every tracked pair where actual_hash != recorded_hash.
    A deleted source has actual_hash = None.
    Sources not touched in paths are never checked or reported.
    """
    norm_paths = {repo.canonical_relpath(os.path.join(repo_root, p), repo_root) for p in paths if p}
    if not norm_paths:
        return []

    mapping = topic_sources(repo_root, read=read)
    drifted: List[Tuple[str, str, Optional[str], Optional[str]]] = []

    for src_rel in sorted(norm_paths):
        if src_rel not in mapping:
            continue
        for topic_rel, rec_hash in mapping[src_rel]:
            if not rec_hash:
                continue  # Untracked source (no recorded hash)

            content = read(src_rel) if read else None
            if content is None and not read:
                full_src = os.path.join(repo_root, src_rel)
                if os.path.isfile(full_src):
                    content = textio.read_text(full_src, strict=False)

            actual_hash = compute_content_hash(content) if content is not None else None
            if actual_hash != rec_hash:
                drifted.append((topic_rel, src_rel, rec_hash, actual_hash))

    return drifted


def resolve_topic_path(repo_root: str, topic_spec: str) -> Optional[str]:
    """Find absolute or canonical path to a topic file from varied CLI inputs."""
    candidates = [
        topic_spec,
        os.path.join("docs", topic_spec),
        os.path.join("docs", f"{topic_spec}.md"),
        os.path.join("docs", f"topic--{topic_spec}.md"),
    ]
    if topic_spec.startswith("topic--"):
        clean = topic_spec[len("topic--"):]
        candidates.append(os.path.join("docs", f"topic--{clean}.md"))
    for cand in candidates:
        full = cand if os.path.isabs(cand) else os.path.join(repo_root, cand)
        if os.path.isfile(full):
            return repo.canonical_relpath(full, repo_root)
    # Search all topic files
    target_clean = topic_spec.replace("topic--", "").replace(".md", "")
    for _, topic_rel in find_all_topic_files(repo_root):
        base = os.path.basename(topic_rel).replace("topic--", "").replace(".md", "")
        if base == target_clean or topic_rel.endswith(topic_spec):
            return topic_rel
    return None


def accept(
    repo_root: str,
    topic_spec: str,
    sources: Optional[Sequence[str]] = None,
) -> Tuple[str, List[Tuple[str, Optional[str], str]]]:
    """Accept current content hashes for drifted sources in a topic.

    Rewrites only the hash values in the front-matter sources list,
    leaving all other front-matter keys and the body byte-identical.

    Returns:
        (canonical_topic_path, [(source_path, old_hash, new_hash), ...])
    """
    topic_rel = resolve_topic_path(repo_root, topic_spec)
    if not topic_rel:
        raise FileNotFoundError(f"Topic article not found for spec '{topic_spec}'.")

    topic_full = os.path.join(repo_root, topic_rel)
    content = textio.read_text(topic_full, strict=False)

    block = frontmatter.split(content)
    if block is None:
        return topic_rel, []

    data = frontmatter._load_block(block, topic_full)
    sources_data = data.get("sources")
    if not sources_data or not isinstance(sources_data, list):
        return topic_rel, []

    ctx_dir = os.path.dirname(os.path.dirname(topic_full))

    target_sources = {s.replace("\\", "/") for s in sources} if sources else None
    accepted: List[Tuple[str, Optional[str], str]] = []

    for item in sources_data:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        if not raw_path:
            continue

        raw_norm = raw_path.replace("\\", "/")
        if target_sources:
            match = (
                raw_norm in target_sources
                or os.path.basename(raw_norm) in target_sources
                or any(raw_norm.endswith(t) for t in target_sources)
            )
            if not match:
                continue

        src_full = os.path.normpath(os.path.join(ctx_dir, raw_path))
        if not os.path.isfile(src_full):
            src_full = os.path.normpath(os.path.join(repo_root, raw_path))

        if not os.path.isfile(src_full):
            continue

        src_text = textio.read_text(src_full, strict=False)
        current_hash = compute_content_hash(src_text)
        old_hash = item.get("hash")
        if current_hash != old_hash:
            item["hash"] = current_hash
            accepted.append((raw_path, old_hash, current_hash))

    if accepted:
        emitted = frontmatter._dump(data).rstrip("\n")
        delim = block.close_delim.lstrip("\r\n")
        updated_content = f"{block.open_delim}{emitted}\n{delim}{block.body}"
        textio.write_text(topic_full, updated_content)

    return topic_rel, accepted


def drift_diff(
    repo_root: str,
    topic_spec: str,
) -> List[Tuple[str, Optional[str], Optional[str], Optional[str]]]:
    """Retrieve git diff for each drifted source of topic from the recording commit.

    Returns:
        [(source_path, commit_hash, diff_output, note)]
    """
    topic_rel = resolve_topic_path(repo_root, topic_spec)
    if not topic_rel:
        raise FileNotFoundError(f"Topic article not found for spec '{topic_spec}'.")

    topic_full = os.path.join(repo_root, topic_rel)
    content = textio.read_text(topic_full, strict=False)
    fm, _ = frontmatter.parse(content, path=topic_rel)

    sources = fm.get("sources")
    if not sources or not isinstance(sources, list):
        return []

    ctx_dir = os.path.dirname(os.path.dirname(topic_full))
    results: List[Tuple[str, Optional[str], Optional[str], Optional[str]]] = []

    for item in sources:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path")
        rec_hash = item.get("hash")
        if not raw_path or not rec_hash:
            continue

        src_full = os.path.normpath(os.path.join(ctx_dir, raw_path))
        if not os.path.isfile(src_full):
            src_full = os.path.normpath(os.path.join(repo_root, raw_path))
        if not os.path.isfile(src_full):
            results.append((raw_path, None, None, "source file does not exist on disk"))
            continue

        src_text = textio.read_text(src_full, strict=False)
        cur_hash = compute_content_hash(src_text)
        if cur_hash == rec_hash:
            continue  # Not drifted

        # Find last commit where topic file contained rec_hash
        log_res = proc.run_capture(
            ["git", "log", "-1", "--format=%H", f"-S{rec_hash}", "--", topic_rel],
            cwd=repo_root,
        )
        commit = log_res.stdout.strip() if log_res.ok else ""
        if commit:
            diff_res = proc.run_capture(
                ["git", "diff", commit, "--", raw_path],
                cwd=repo_root,
            )
            diff_text = diff_res.stdout if diff_res.ok else ""
            results.append((raw_path, commit, diff_text, None))
        else:
            results.append((raw_path, None, None, "no commit recorded this hash"))

    return results
