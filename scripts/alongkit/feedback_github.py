#!/usr/bin/env python3
"""
alongkit.feedback_github - GitHub Pull Request Transport and Web Fallback.

Builds sanitized feedback notes for .along/inbox/ and dispatches them directly
to the Along repository via GitHub API (gh) or browser web fallback.
"""

from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
import tempfile
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

if __name__ == "__main__":
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along --help   (or: python scripts/along_exec.py --help)"
    )

from alongkit import frontmatter, proc, typography, version
from alongkit.diagnostics import EXPORT_DIR, Redactor


def build_inbox_note(
    title: str,
    body: str,
    incidents: Optional[List[Dict[str, Any]]] = None,
    date: Optional[str] = None
) -> Tuple[str, str]:
    """Build an inbox feedback note Markdown document with front-matter.

    Sanitizes all PII/secrets, normalizes typography to pure ASCII, and returns
    (relative_inbox_path, rendered_document_text).
    """
    clean_title = Redactor.sanitize_text(title)
    clean_title, _ = typography.clean(clean_title)
    clean_title = clean_title.strip()

    raw_slug = re.sub(r"[^a-z0-9]+", "-", clean_title.lower()).strip("-")
    if not raw_slug:
        raw_slug = "feedback"
    slug = raw_slug[:50].rstrip("-")
    if not slug:
        slug = "feedback"

    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    rel_path = f".along/inbox/feedback--{date}-{slug}.md"

    meta: Dict[str, Any] = {
        "title": clean_title,
        "date": date,
        "along_version": str(version.CURRENT_VERSION),
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "source": "along-feedback",
        "tags": ["feedback"],
    }

    body_clean = Redactor.sanitize_text(body)
    body_clean, _ = typography.clean(body_clean)

    content_parts = [body_clean.strip()]

    if incidents:
        incident_lines = ["\n## Incidents\n"]
        for inc in incidents:
            inc_id = inc.get("id", "")
            comp = inc.get("component", "")
            err = inc.get("error_message", "")[:200]

            inc_id_clean = Redactor.sanitize_text(str(inc_id))
            comp_clean = Redactor.sanitize_text(str(comp))
            err_clean = Redactor.sanitize_text(str(err))

            inc_id_clean, _ = typography.clean(inc_id_clean)
            comp_clean, _ = typography.clean(comp_clean)
            err_clean, _ = typography.clean(err_clean)

            incident_lines.append(
                f"- ID: {inc_id_clean}\n  Component: {comp_clean}\n  Error: {err_clean}\n"
            )
        content_parts.append("".join(incident_lines).strip())

    full_body = "\n\n".join(part for part in content_parts if part).strip()

    rendered = frontmatter.render(meta, full_body)
    rendered = Redactor.sanitize_text(rendered)
    rendered, _ = typography.clean(rendered)

    return rel_path, rendered


class GitHubTransport:
    """Dispatches feedback notes via GitHub CLI (gh) PR or Web fallback."""

    DEFAULT_REPO = "actdim/along"
    URL_LENGTH_LIMIT = 7000

    @classmethod
    def send(
        cls,
        title: str,
        body: str,
        incidents: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
        yes: bool = False,
        dry_run: bool = False,
        repo_root: Optional[str] = None,
        which: Optional[Callable[[str], Optional[str]]] = None,
        run: Optional[Callable[..., Any]] = None,
        open_url: Optional[Callable[[str], bool]] = None,
        date: Optional[str] = None,
        export_dir: Optional[str] = None,
    ) -> Tuple[bool, str]:
        which_fn = which or shutil.which
        run_fn = run or proc.run_capture
        open_url_fn = open_url or webbrowser.open
        export_dir_path = export_dir or EXPORT_DIR

        target_repo = os.environ.get("ALONG_FEEDBACK_GITHUB_REPO")
        if not target_repo and config:
            target_repo = config.get("transports", {}).get("github", {}).get("repo")
        if not target_repo:
            target_repo = cls.DEFAULT_REPO
        target_repo = target_repo.strip()

        rel_path, note_text = build_inbox_note(
            title=title, body=body, incidents=incidents, date=date
        )

        clean_title = Redactor.sanitize_text(title)
        clean_title, _ = typography.clean(clean_title)
        clean_title = clean_title.strip()

        raw_slug = re.sub(r"[^a-z0-9]+", "-", clean_title.lower()).strip("-")
        if not raw_slug:
            raw_slug = "feedback"
        slug = raw_slug[:50].rstrip("-") or "feedback"

        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not yes or dry_run:
            print(f"-> Target Note Path: {rel_path}")
            print("-> Note Content:")
            print("-" * 60)
            print(note_text)
            print("-" * 60)
            print("-> Planned Actions:")
            print(f"   - Target repository: {target_repo}")
            print("   - Check GitHub CLI (gh) authentication")
            print("   - If gh authenticated: create branch, commit note under .along/inbox/, open Pull Request")
            print("   - If gh missing/unauthenticated: open pre-filled GitHub new file web editor in browser")
            print("[Notice] Preview mode: explicit confirmation (--yes) required to dispatch.")
            print("NOT SENT")
            return True, "Preview only (NOT SENT without --yes)."

        gh_bin = which_fn("gh")
        if not gh_bin:
            print(
                "GitHub CLI (gh) not found: with gh this would be fully automatic. "
                "Install it and run `gh auth login` to skip the browser next time. "
                "Opening the GitHub page instead."
            )
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )

        auth_res = run_fn(["gh", "auth", "status"])
        if auth_res.returncode != 0:
            print(
                "GitHub CLI (gh) not authenticated: with gh this would be fully automatic. "
                "Install it and run `gh auth login` to skip the browser next time. "
                "Opening the GitHub page instead."
            )
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )

        user_res = run_fn(["gh", "api", "user", "--jq", ".login"])
        if user_res.returncode != 0:
            err = (user_res.stderr or user_res.stdout).strip()
            print(f"GitHub CLI error: {err}")
            print("Automatic path failed; falling back to web browser.")
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )
        login = user_res.stdout.strip()

        push_res = run_fn(["gh", "api", f"repos/{target_repo}", "--jq", ".permissions.push"])
        if push_res.returncode != 0:
            err = (push_res.stderr or push_res.stdout).strip()
            print(f"GitHub CLI error: {err}")
            print("Automatic path failed; falling back to web browser.")
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )
        is_collaborator = (push_res.stdout.strip() == "true")

        repo_name = target_repo.split("/")[-1]

        if is_collaborator:
            target_write_repo = target_repo
            head_owner = login
        else:
            fork_res = run_fn(
                ["gh", "repo", "fork", target_repo, "--clone=false", "--default-branch-only"]
            )
            if fork_res.returncode != 0:
                err = (fork_res.stderr or fork_res.stdout).strip()
                print(f"GitHub CLI error: {err}")
                print("Automatic path failed; falling back to web browser.")
                return cls._web_fallback(
                    target_repo=target_repo,
                    rel_path=rel_path,
                    note_text=note_text,
                    date=date,
                    slug=slug,
                    export_dir=export_dir_path,
                    open_url_fn=open_url_fn,
                )

            fork_repo = f"{login}/{repo_name}"
            parent_res = run_fn(
                ["gh", "api", f"repos/{login}/{repo_name}", "--jq", ".parent.full_name"]
            )
            if parent_res.returncode != 0:
                err = (parent_res.stderr or parent_res.stdout).strip()
                print(f"GitHub CLI error: {err}")
                print("Automatic path failed; falling back to web browser.")
                return cls._web_fallback(
                    target_repo=target_repo,
                    rel_path=rel_path,
                    note_text=note_text,
                    date=date,
                    slug=slug,
                    export_dir=export_dir_path,
                    open_url_fn=open_url_fn,
                )
            parent_full_name = parent_res.stdout.strip()
            if parent_full_name != target_repo:
                err = f"Fork parent '{parent_full_name}' does not match target repo '{target_repo}'."
                print(f"GitHub CLI error: {err}")
                print("Automatic path failed; falling back to web browser.")
                return cls._web_fallback(
                    target_repo=target_repo,
                    rel_path=rel_path,
                    note_text=note_text,
                    date=date,
                    slug=slug,
                    export_dir=export_dir_path,
                    open_url_fn=open_url_fn,
                )

            run_fn(
                ["gh", "api", "-X", "POST", f"repos/{fork_repo}/merge-upstream", "-f", "branch=main"]
            )
            target_write_repo = fork_repo
            head_owner = login

        base_sha_res = run_fn(
            ["gh", "api", f"repos/{target_repo}/git/ref/heads/main", "--jq", ".object.sha"]
        )
        if base_sha_res.returncode != 0:
            err = (base_sha_res.stderr or base_sha_res.stdout).strip()
            print(f"GitHub CLI error: {err}")
            print("Automatic path failed; falling back to web browser.")
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )
        base_sha = base_sha_res.stdout.strip()

        branch_base = f"feedback/{date}-{slug}"
        branch = branch_base
        branch_created = False
        last_branch_err = ""

        for attempt in range(1, 10):
            if attempt == 1:
                branch = branch_base
            else:
                branch = f"{branch_base}-{attempt}"

            ref_res = run_fn([
                "gh", "api", "-X", "POST", f"repos/{target_write_repo}/git/refs",
                "-f", f"ref=refs/heads/{branch}",
                "-f", f"sha={base_sha}",
            ])
            if ref_res.returncode == 0:
                branch_created = True
                break

            err_text = ((ref_res.stderr or "") + " " + (ref_res.stdout or "")).lower()
            last_branch_err = (ref_res.stderr or ref_res.stdout or "").strip()
            if "already exists" in err_text or "422" in err_text:
                continue
            else:
                break

        if not branch_created:
            print(f"GitHub CLI error: {last_branch_err}")
            print("Automatic path failed; falling back to web browser.")
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )

        b64_content = base64.b64encode(note_text.encode("utf-8")).decode("ascii")
        put_payload = {
            "message": f"feedback: {clean_title}",
            "content": b64_content,
            "branch": branch,
        }

        temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
        try:
            with open(temp_fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(put_payload, f)

            put_res = run_fn([
                "gh", "api", "-X", "PUT", f"repos/{target_write_repo}/contents/{rel_path}",
                "--input", temp_path,
            ])
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        if put_res.returncode != 0:
            err = (put_res.stderr or put_res.stdout).strip()
            print(f"GitHub CLI error: {err}")
            print("Automatic path failed; falling back to web browser.")
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )

        head_arg = f"{head_owner}:{branch}"
        pr_body = f"Automated feedback submitted via Along Protocol v{version.CURRENT_VERSION}."
        pr_res = run_fn([
            "gh", "pr", "create",
            "--repo", target_repo,
            "--base", "main",
            "--head", head_arg,
            "--title", f"feedback: {clean_title}",
            "--body", pr_body,
        ])
        if pr_res.returncode != 0:
            err = (pr_res.stderr or pr_res.stdout).strip()
            print(f"GitHub CLI error: {err}")
            print("Automatic path failed; falling back to web browser.")
            return cls._web_fallback(
                target_repo=target_repo,
                rel_path=rel_path,
                note_text=note_text,
                date=date,
                slug=slug,
                export_dir=export_dir_path,
                open_url_fn=open_url_fn,
            )

        pr_url = pr_res.stdout.strip()
        print(f"-> Pull request created: {pr_url}")
        return True, pr_url

    @classmethod
    def _web_fallback(
        cls,
        target_repo: str,
        rel_path: str,
        note_text: str,
        date: str,
        slug: str,
        export_dir: str,
        open_url_fn: Callable[[str], bool],
    ) -> Tuple[bool, str]:
        base_url = f"https://github.com/{target_repo}/new/main?filename={urllib.parse.quote(rel_path)}&value="
        encoded_full = urllib.parse.quote(note_text)
        full_url = base_url + encoded_full

        if len(full_url) > cls.URL_LENGTH_LIMIT:
            os.makedirs(export_dir, exist_ok=True)
            export_file = os.path.join(export_dir, f"feedback-full--{date}-{slug}.md")
            with open(export_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(note_text)

            redacted_export_path = Redactor.sanitize_text(export_file)
            redacted_export_path, _ = typography.clean(redacted_export_path)

            trunc_notice = (
                f"\n\n...[Body truncated due to URL length limit. Full report saved to: {redacted_export_path}]"
            )
            budget = cls.URL_LENGTH_LIMIT - len(base_url)

            trimmed = note_text
            while trimmed and (len(urllib.parse.quote(trimmed + trunc_notice)) > budget):
                trimmed = trimmed[: max(0, len(trimmed) - 100)]

            while trimmed and (len(urllib.parse.quote(trimmed + trunc_notice)) > budget):
                trimmed = trimmed[:-1]

            final_body = trimmed + trunc_notice
            full_url = base_url + urllib.parse.quote(final_body)
            print(f"Saved full feedback note to: {redacted_export_path}")
            print("Please attach or paste the full note into the pull request description.")

        open_url_fn(full_url)
        print(f"Opened GitHub web fallback: {full_url}")
        print("Click 'Propose changes', then 'Create pull request'; the PR link appears there.")
        return True, full_url
