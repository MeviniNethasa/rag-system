"""Decide how a question should be looked up.

- part_no: the query contains an 8-character alphanumeric code with at least
  one digit (e.g. Dh201079, 30151033, LAC00197). The digit rule keeps
  8-letter words like "ASSEMBLY" from being read as codes.
- sr_no: "part 13", "item 12", "sr no 5", "sr. no. 5", "#13",
  "diagram number 13", "no. 7" (a 1-2 digit number).
- description: everything else; stopword-filtered words become keyword terms.

A part code wins over a Sr. No. when both appear.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PART_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{8}(?![A-Za-z0-9])")

_SR_NO_RE = re.compile(
    r"""(?ix)
    (?:
        \b(?:part|item|sr\.?\s*no\.?|serial(?:\s+(?:no\.?|number))?|
            diagram(?:\s+(?:no\.?|number|item|part))?|no\.?|number|ref(?:erence)?)
        \s*(?:\#|no\.?|number)?\s*[:\-]?\s*
      | \#\s*
    )
    (?P<n>\d{1,2})\b(?![./\-]\d)
    """
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")

STOPWORDS = {
    "a", "about", "all", "an", "and", "any", "are", "as", "at", "be", "can",
    "code", "could", "describe", "description", "details", "do", "does",
    "find", "for", "from", "front", "get", "give", "have", "how", "i", "in",
    "info", "information", "is", "it", "item", "items", "list", "look", "lookup",
    "many", "me", "my", "need", "number", "of", "on", "or", "part", "parts",
    "please", "pulsar", "qty", "quantity", "search", "show", "tell", "that",
    "the", "there", "this", "to", "used", "uses", "wheel", "assembly",
    "what", "whats", "where", "which", "with", "you", "bajaj",
}
# "front", "wheel" and "assembly" describe the whole section, so as keywords
# they would match too broadly (WHEEL FRONT, AXLE - FRONT, SPACER ASSEMBLY).
# They still feed the vector search through the full query text.

_WHOLE_ASSEMBLY_RE = re.compile(
    r"(?i)\b(all|every|whole|entire|full|complete|list)\b.*\b(parts?|items?|assembly|list)\b"
    r"|\bhow many (parts|items)\b|\bwhat(?:'s| is) in\b"
)


@dataclass(frozen=True)
class Route:
    mode: str                         # "part_no" | "sr_no" | "description"
    value: str | None = None          # the code or Sr. No.
    terms: list[str] = field(default_factory=list)
    whole_assembly: bool = False


def find_part_codes(text: str) -> list[str]:
    return _PART_CODE_RE.findall(text)


def keyword_terms(text: str) -> list[str]:
    seen: list[str] = []
    for word in _WORD_RE.findall(text):
        w = word.lower()
        if len(w) < 3 or w in STOPWORDS or w in seen:
            continue
        seen.append(w)
    return seen


def route(query: str) -> Route:
    q = query.strip()
    whole = bool(_WHOLE_ASSEMBLY_RE.search(q))

    codes = find_part_codes(q)
    if codes:
        return Route("part_no", value=codes[0], whole_assembly=whole)

    m = _SR_NO_RE.search(q)
    if m:
        n = str(int(m["n"]))  # "07" -> "7"
        return Route("sr_no", value=n, whole_assembly=whole)

    return Route("description", terms=keyword_terms(q), whole_assembly=whole)
