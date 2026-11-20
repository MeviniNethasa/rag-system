"""Answer from retrieved rows with Claude, then check part-number casing."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .config import claude_model, require_env
from .query_router import find_part_codes
from .retriever import Result

SYSTEM_PROMPT = """You are a spare-parts lookup assistant for a Bajaj motorcycle parts catalogue.

Answer only from the catalogue rows provided in the user message. If they do not \
answer the question, say the part was not found in this assembly; never guess \
part numbers, quantities or descriptions.

Part numbers are case-sensitive identifiers. Copy every Part No. exactly as it \
appears in the rows, character for character, keeping its upper/lower case \
(for example "Dh201079" must stay "Dh201079", never "DH201079"). If the user \
typed a part number in different casing, refer to it as "your search" rather \
than repeating their spelling, and give the stored Part No.

When you mention a part, include its Sr. No. (the diagram number), Part No., \
Description and Qty. Keep answers short; a small list is fine when several \
rows match."""


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
    """Return codes in `text` that don't exactly match a code in the retrieved
    chunks. Catches casing drift such as 'DH201079' for stored 'Dh201079'."""
    allowed: set[str] = set()
    for h in result.hits:
        allowed.update(find_part_codes(h.content))
        if "part_no" in h.metadata:
            allowed.add(h.metadata["part_no"])
    return [c for c in dict.fromkeys(find_part_codes(text)) if c not in allowed]


def answer(result: Result) -> Answer:
    model = claude_model()
    notes = "\n".join(f"Note: {n}" for n in result.notes)
    user_content = (
        f"<catalogue_rows>\n{build_context(result)}\n</catalogue_rows>\n"
        + (f"{notes}\n" if notes else "")
        + f"\nQuestion: {result.query}"
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
