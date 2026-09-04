#!/usr/bin/env python3
"""
alongkit.typography - The single forbidden-character table.

The protocol bans non-ASCII typography and invisible characters in repository text.
Three places encoded that rule independently: the replacement map in
`scripts/sanitize_typography.py`, a separate detection dictionary in
`tests/test_skills_and_scripts.py` (`test_05_clean_typography`), and prose in
`AGENTS.md`. They did not agree, so a character could be banned by the gate and
unknown to the sanitizer, or the reverse.

Characters are written as `\\uXXXX` escapes on purpose: the protocol forbids the
literal glyphs in repository text, including in this file.

Scope note: this module only defines the table and the pure string transformation.
Which files the rule governs is a policy question handled by the sanitizer and its
issue `[bug--typography-sanitizer-destroys-non-utf8-files]`; nothing here reads or
writes files.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python scripts/sanitize_typography.py"
    )


from typing import Dict, Iterable, List, Tuple

#: Replacement map from banned character to its ASCII equivalent.
REPLACEMENTS: Dict[str, str] = {
    # Dashes, hyphens and minuses
    "\u2014": "-",      # em dash
    "\u2013": "-",      # en dash
    "\u2212": "-",      # math minus
    "\u2011": "-",      # non-breaking hyphen
    "\u2012": "-",      # figure dash
    "\u2015": "-",      # horizontal bar

    # Quotes and apostrophes
    "\u201c": '"',      # left double quotation mark
    "\u201d": '"',      # right double quotation mark
    "\u2018": "'",      # left single quotation mark
    "\u2019": "'",      # right single quotation mark / apostrophe
    "\u201a": "'",      # single low-9 quotation mark
    "\u201e": '"',      # double low-9 quotation mark
    "\u00ab": '"',      # left-pointing double angle quotation mark
    "\u00bb": '"',      # right-pointing double angle quotation mark
    "\u2032": "'",      # prime
    "\u2033": '"',      # double prime
    "\u2035": "'",      # reversed prime

    # Ellipsis
    "\u2026": "...",    # horizontal ellipsis

    # Bullets
    "\u2022": "-",      # bullet
    "\u2023": "-",      # triangular bullet
    "\u2043": "-",      # hyphen bullet

    # Invisible and special whitespace
    "\u00a0": " ",      # non-breaking space
    "\u2007": " ",      # figure space
    "\u202f": " ",      # narrow non-breaking space
    "\u3000": " ",      # ideographic space
    "\u2002": " ",      # en space
    "\u2003": " ",      # em space
    "\u2009": " ",      # thin space
    "\u200a": " ",      # hair space
    "\u200b": "",       # zero-width space
    "\u200c": "",       # zero-width non-joiner
    "\u200d": "",       # zero-width joiner
    "\ufeff": "",       # zero-width no-break space / byte order mark
}

#: Human-readable names, for gate messages that must say what was found and where.
NAMES: Dict[str, str] = {
    "\u2014": "em dash",
    "\u2013": "en dash",
    "\u2212": "math minus",
    "\u2011": "non-breaking hyphen",
    "\u2012": "figure dash",
    "\u2015": "horizontal bar",
    "\u201c": "left curly double quote",
    "\u201d": "right curly double quote",
    "\u2018": "left curly single quote",
    "\u2019": "right curly single quote",
    "\u201a": "single low-9 quote",
    "\u201e": "double low-9 quote",
    "\u00ab": "left guillemet",
    "\u00bb": "right guillemet",
    "\u2032": "prime",
    "\u2033": "double prime",
    "\u2035": "reversed prime",
    "\u2026": "ellipsis glyph",
    "\u2022": "bullet glyph",
    "\u2023": "triangular bullet",
    "\u2043": "hyphen bullet",
    "\u00a0": "non-breaking space",
    "\u2007": "figure space",
    "\u202f": "narrow non-breaking space",
    "\u3000": "ideographic space",
    "\u2002": "en space",
    "\u2003": "em space",
    "\u2009": "thin space",
    "\u200a": "hair space",
    "\u200b": "zero-width space",
    "\u200c": "zero-width non-joiner",
    "\u200d": "zero-width joiner",
    "\ufeff": "byte order mark",
}

EM_DASH = "\u2014"
BOM = "\ufeff"


def name_of(char: str) -> str:
    """Readable name of a banned character, falling back to its code point."""
    return NAMES.get(char, "U+%04X" % ord(char))


def clean(text: str) -> Tuple[str, bool]:
    """Return `(cleaned_text, changed)` with every banned character replaced.

    An em dash surrounded by spaces becomes a spaced hyphen first, so the common
    " word - word " form reads correctly instead of collapsing the spacing.
    """
    cleaned = text
    spaced_em = f" {EM_DASH} "
    if spaced_em in cleaned:
        cleaned = cleaned.replace(spaced_em, " - ")
    for char, replacement in REPLACEMENTS.items():
        if char in cleaned:
            cleaned = cleaned.replace(char, replacement)
    return cleaned, cleaned != text


def findings(text: str, chars: Iterable[str] = ()) -> List[Tuple[int, int, str]]:
    """Locate banned characters as `(line, column, character)`, both 1-based.

    Used by a gate that must report where a violation is, rather than only that the
    repository contains one somewhere.
    """
    banned = set(chars) or set(REPLACEMENTS)
    hits: List[Tuple[int, int, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for column, char in enumerate(line, 1):
            if char in banned:
                hits.append((line_number, column, char))
    return hits
