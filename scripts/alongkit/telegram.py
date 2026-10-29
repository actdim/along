#!/usr/bin/env python3
"""
alongkit.telegram - Centralized Telegram client, settings resolution, and dispatch helpers.

Consolidates Telegram configuration resolution, sendMessage dispatch, and Bot API error
handling used by the runner daemon and feedback diagnostics.
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along doctor   (or: python scripts/along_exec.py doctor)"
    )

from dataclasses import dataclass, field
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from . import repo

API_BASE: str = "https://api.telegram.org"
MAX_MESSAGE_CHARS: int = 4000
TOKEN_ENV_VARS: Tuple[str, ...] = ("TELEGRAM_BOT_TOKEN", "ALONG_TELEGRAM_BOT_TOKEN")
CHAT_ENV_VARS: Tuple[str, ...] = ("TELEGRAM_CHAT_ID", "ALONG_TELEGRAM_CHAT_ID")


class TelegramAuthError(RuntimeError):
    """The Bot API rejected the token (HTTP 401/404); retrying cannot help."""


class TelegramConflictError(RuntimeError):
    """Another getUpdates consumer or webhook holds the bot token (HTTP 409)."""


class TelegramRateLimitError(RuntimeError):
    """The Bot API rate-limited getUpdates (HTTP 429); carries retry_after."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class TelegramSettings:
    """Resolved Telegram credentials and operational state."""

    bot_token: str = ""
    chat_ids: List[str] = field(default_factory=list)
    enabled: bool = False
    _primary_chat_id: str = ""

    @property
    def primary_chat_id(self) -> str:
        """The first id from the highest-precedence source that set any."""
        if self._primary_chat_id:
            return self._primary_chat_id
        return self.chat_ids[0] if self.chat_ids else ""


def settings_from_sections(
    sections: Sequence[Mapping[str, Any]],
    environ: Optional[Mapping[str, str]] = None,
) -> TelegramSettings:
    """Pure configuration resolver combining sections (in rising precedence) and environment."""
    env = os.environ if environ is None else environ
    bot_token = ""
    chat_ids: List[str] = []
    enabled = False
    primary_chat_id = ""

    for sec in sections:
        if not isinstance(sec, (dict, Mapping)):
            continue
        tok = sec.get("bot_token")
        if tok and str(tok).strip():
            bot_token = str(tok).strip()

        raw_cids: List[str] = []
        if sec.get("chat_id"):
            raw_cids.append(str(sec["chat_id"]).strip())
        if sec.get("chat_ids") and isinstance(sec["chat_ids"], (list, tuple)):
            for cid in sec["chat_ids"]:
                raw_cids.append(str(cid).strip())

        valid_cids = [c for c in raw_cids if c]
        if valid_cids:
            primary_chat_id = valid_cids[0]
            for cid in valid_cids:
                if cid not in chat_ids:
                    chat_ids.append(cid)

        if sec.get("enabled") is not None:
            enabled = bool(sec.get("enabled"))

    # Environment overrides (authoritative)
    env_token = ""
    for var in TOKEN_ENV_VARS:
        val = env.get(var)
        if val and val.strip():
            env_token = val.strip()
            break
    if env_token:
        bot_token = env_token
        enabled = True

    env_chats: List[str] = []
    for var in CHAT_ENV_VARS:
        val = env.get(var)
        if val and val.strip():
            for part in val.split(","):
                clean = part.strip()
                if clean:
                    env_chats.append(clean)
            break

    if env_chats:
        primary_chat_id = env_chats[0]
        for cid in env_chats:
            if cid not in chat_ids:
                chat_ids.append(cid)
        enabled = True

    return TelegramSettings(
        bot_token=bot_token,
        chat_ids=chat_ids,
        enabled=enabled,
        _primary_chat_id=primary_chat_id,
    )


def resolve_settings(
    repo_root: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    global_config: Optional[str] = None,
) -> TelegramSettings:
    """Resolve Telegram settings from global config, local repo config, and environment."""
    sections: List[Dict[str, Any]] = []

    global_path = global_config if global_config is not None else os.path.expanduser("~/.along/config.json")
    if global_path and os.path.isfile(global_path):
        try:
            with open(global_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    t_sec = loaded.get("transports", {}).get("telegram")
                    if isinstance(t_sec, dict):
                        sections.append(t_sec)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            pass

    if repo_root:
        local_path = os.path.join(repo.state_dir(repo_root), "config.json")
        if os.path.isfile(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        t_sec = loaded.get("transports", {}).get("telegram")
                        if isinstance(t_sec, dict):
                            sections.append(t_sec)
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                pass

    return settings_from_sections(sections, environ=environ)


def send_message(
    bot_token: str,
    chat_id: Union[int, str],
    text: str,
    *,
    base_url: str = API_BASE,
    timeout: float = 10.0,
) -> Tuple[bool, str]:
    """Send a plain text message to the specified Telegram chat.

    Returns (success: bool, detail: str). On failure detail describes the error
    without exposing the bot token.
    """
    token = bot_token.strip()
    cid = str(chat_id).strip()
    if not token or not cid:
        return False, "Telegram credentials missing."

    msg = text[:MAX_MESSAGE_CHARS]
    url = f"{base_url.rstrip('/')}/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": msg,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Along/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                raw = resp.read()
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                if isinstance(parsed, dict) and parsed.get("ok"):
                    return True, "Successfully dispatched message."
                return False, "Telegram API returned ok: false"
            return False, f"Telegram API returned status {resp.status}."
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"Network error: {exc.reason}"
    except (OSError, ValueError, TypeError, TimeoutError) as exc:
        return False, f"Network error: {exc}"


class TelegramClient:
    """Standard library HTTP client for Telegram Bot API."""

    def __init__(self, bot_token: str, base_url: str = API_BASE) -> None:
        self.bot_token = bot_token.strip()
        self.raw_base_url = base_url.rstrip("/")
        self.base_url = f"{self.raw_base_url}/bot{self.bot_token}"

    def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch incoming updates using long polling."""
        params: Dict[str, Any] = {
            "timeout": timeout,
            "limit": limit,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            params["offset"] = offset

        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/getUpdates?{query}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Along-Runner-Daemon/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout + 15) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        res = data.get("result", [])
                        return res if isinstance(res, list) else []
        except urllib.error.HTTPError as exc:
            # The URL holds the token: report the status only.
            if exc.code in (401, 404):
                raise TelegramAuthError(f"getUpdates rejected the bot token (HTTP {exc.code})") from None
            if exc.code == 409:
                raise TelegramConflictError(
                    "getUpdates HTTP 409: another consumer uses this bot token (another daemon or a webhook)"
                ) from None
            if exc.code == 429:
                retry_after: Optional[float] = None
                try:
                    raw_body = exc.read().decode("utf-8")
                    data = json.loads(raw_body)
                    ra = data.get("parameters", {}).get("retry_after")
                    if ra is not None:
                        val = float(ra)
                        retry_after = int(val) if val.is_integer() else val
                except (OSError, ValueError, TypeError, AttributeError):
                    pass
                ra_str = f", retry_after={retry_after}" if retry_after is not None else ""
                raise TelegramRateLimitError(
                    f"getUpdates rate limited (HTTP 429{ra_str})",
                    retry_after=retry_after,
                ) from None
            raise RuntimeError(f"getUpdates HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError, ValueError, TypeError, TimeoutError) as exc:
            raise RuntimeError(f"getUpdates network error: {exc}") from exc
        return []

    def send_message(self, chat_id: Union[int, str], text: str) -> bool:
        """Send a plain text message to the specified Telegram chat."""
        ok, _ = send_message(self.bot_token, chat_id, text, base_url=self.raw_base_url, timeout=10.0)
        return ok
