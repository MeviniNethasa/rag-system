"""Offline tests for the casing safety check and the fallback query rewrite."""

from parts_rag.llm import _question_for_llm, check_casing
from parts_rag.query_router import route
from parts_rag.retriever import Hit, Result

SENSOR = Hit(
    id="28-row-16",
    content="Model: Pulsar N-125 (00JZF7ZZ) | Sr. No.: 16 | Part No.: Dh201079 | Description: SENSOR SPEED-ASSY | Qty: 1",
    metadata={"chunk_type": "row", "sr_no": "16", "part_no": "Dh201079",
              "description": "SENSOR SPEED-ASSY", "qty": 1},
    source="ci_fallback",
)


def _result(query, hits, mode):
    return Result(query=query, route=route(query), hits=hits, lookup_mode=mode)


def test_correct_casing_passes():
    res = _result("DH201079", [SENSOR], "ci_fallback")
    assert check_casing("Part No. Dh201079 is the speed sensor.", res) == []


def test_wrong_casing_of_stored_code_fails():
    res = _result("DH201079", [SENSOR], "ci_fallback")
    assert check_casing("Your search DH201079 matched Dh201079.", res) == ["DH201079"]


def test_invented_code_fails():
    res = _result("speed sensor", [SENSOR], "hybrid")
    assert check_casing("Try AB123456 instead.", res) == ["AB123456"]


def test_echoing_unmatched_query_code_is_allowed():
    res = _result("XX999999", [], "none")
    assert check_casing("Part No. XX999999 was not found.", res) == []


def test_fallback_rewrites_question_to_stored_casing():
    res = _result("what is DH201079?", [SENSOR], "ci_fallback")
    question, notes = _question_for_llm(res)
    assert question == "what is Dh201079?"
    assert all("DH201079" not in n for n in notes)


def test_exact_match_question_unchanged():
    res = _result("Dh201079", [SENSOR], "exact")
    assert _question_for_llm(res)[0] == "Dh201079"
