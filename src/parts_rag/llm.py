"""Answer from retrieved rows with Claude, then check part-number casing."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .config import claude_model, require_env
from .query_router import find_part_codes
from .retriever import Result

SYSTEM_PROMPT = """You are a spare-parts lookup assistant for a Bajaj motorcycle parts catalogue. \
Your reply is printed in a plain terminal.

Answer only from the catalogue rows in the user message. If they don't answer \
the question, reply with one line saying it isn't in this assembly; never guess \
part numbers, quantities or descriptions.

Part numbers are case-sensitive. Copy every Part No. exactly as it appears in \
the rows, keeping its upper/lower case ("Dh201079" stays "Dh201079").

Style:
- Answer in one or two short lines. Start directly with the answer: no \
preamble such as "Based on your search", no closing offers or follow-up questions.
- Mention each part exactly once, in this form: \
Part No. Dh201079 - SENSOR SPEED-ASSY (Sr. No. 16, Qty 1)
- When several parts match, put each on its own line in that form, with no \
extra commentary.
- Plain text only: no markdown, bold, headings or bullet symbols."""


@dataclass
class Answer:
    text: str
    model: str
    casing_ok: bool
    unknown_codes: list[str] = field(default_factory=list)
    stop_reason: str | None = None


@lru_cache(maxsize=1)
def _client():
    import anthropic

    return anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))


def build_context(result: Result) -> str:
    if not result.hits:
        return "(no catalogue rows matched)"
    blocks = []
    for h in result.hits:
        m = h.metadata
        if h.is_row:
            blocks.append(
                f"- Sr. No. {m['sr_no']} | Part No. {m['part_no']} | "
                f"{m['description']} | Qty {m['qty']}"
                + (f" | Remark {m['remark']}" if m.get("remark") else "")
            )
        else:
            blocks.append(h.content)
    header = (
        f"Model: {result.hits[0].metadata.get('model')} "
        f"({result.hits[0].metadata.get('model_code')})\n"
        f"Assembly: {result.hits[0].metadata.get('assembly')}"
    )
    return header + "\n" + "\n".join(blocks)


def check_casing(text: str, result: Result) -> list[str]:
    """Return codes in `text` that are a different-case copy of a retrieved
    code (e.g. 'DH201079' for stored 'Dh201079') or that appear nowhere in
    the retrieved chunks or the user's question.

    A code the user typed that matches nothing at all (e.g. 'XX999999' in a
    "not found" reply) is allowed: echoing it is not a casing error."""
    allowed: set[str] = set()
    for h in result.hits:
        allowed.update(find_part_codes(h.content))
        if "part_no" in h.metadata:
            allowed.add(h.metadata["part_no"])
    allowed_lower = {c.lower() for c in allowed}
    for c in find_part_codes(result.query):
        if c.lower() not in allowed_lower:
            allowed.add(c)
    return [c for c in dict.fromkeys(find_part_codes(text)) if c not in allowed]


def _question_for_llm(result: Result) -> tuple[str, list[str]]:
    """On a case-insensitive fallback, replace the user's typed code with the
    stored Part No. so Claude never sees (or repeats) the wrong casing."""
    question, notes = result.query, list(result.notes)
    if result.lookup_mode == "ci_fallback" and result.rows:
        stored = result.rows[0].metadata["part_no"]
        question = question.replace(result.route.value, stored)
        notes = [
            f"The user's search matched Part No. {stored} case-insensitively. "
            f"Write it only as {stored}."
        ]
    return question, notes


def answer(result: Result) -> Answer:
    model = claude_model()
    question, notes = _question_for_llm(result)
    note_text = "\n".join(f"Note: {n}" for n in notes)
    user_content = (
        f"<catalogue_rows>\n{build_context(result)}\n</catalogue_rows>\n"
        + (f"{note_text}\n" if note_text else "")
        + f"\nQuestion: {question}"
    )
    response = _client().messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "refusal":
        text = text or "(The model declined to answer this request.)"
    unknown = check_casing(text, result)
    return Answer(
        text=text,
        model=model,
        casing_ok=not unknown,
        unknown_codes=unknown,
        stop_reason=response.stop_reason,
    )
