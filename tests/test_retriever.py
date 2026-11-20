"""Offline tests for retriever.py: the database and embedder are faked."""

import pytest

from parts_rag import retriever


def _row(sr, part, desc, **extra):
    return {
        "id": f"28-row-{int(sr):02d}",
        "content": f"Model: Pulsar N-125 (00JZF7ZZ) | Sr. No.: {sr} | Part No.: {part} | Description: {desc} | Qty: 1",
        "metadata": {"chunk_type": "row", "sr_no": str(sr), "part_no": part,
                     "description": desc, "qty": 1},
        **extra,
    }


SUMMARY = {"id": "28-summary", "content": "Full parts list", "similarity": 0.7,
           "metadata": {"chunk_type": "summary"}}


@pytest.fixture
def fake_db(monkeypatch):
    calls = {"vectors": 0}
    state = {"keyword": [], "vector": []}

    def match_description(terms):
        return state["keyword"]

    def match_vectors(embedding, match_count=8, min_similarity=0.0):
        calls["vectors"] += 1
        return state["vector"]

    monkeypatch.setattr(retriever.db, "match_description", match_description)
    monkeypatch.setattr(retriever.db, "match_vectors", match_vectors)
    monkeypatch.setattr(retriever, "embed_query", lambda q: [0.0] * 384)
    return state, calls


def test_keyword_hits_skip_vector_search(fake_db):
    state, calls = fake_db
    state["keyword"] = [_row(11, "JZ131949", "DISC BRAKE DIA 240", matched_terms=1)]
    state["vector"] = [_row(4, "DJ151041", "AXLE - FRONT", similarity=0.8)]

    res = retriever.retrieve("disc")

    assert [h.metadata["part_no"] for h in res.hits] == ["JZ131949"]
    assert res.lookup_mode == "keyword"
    assert calls["vectors"] == 0


def test_keyword_hits_ranked_by_terms_matched(fake_db):
    state, _ = fake_db
    state["keyword"] = [
        _row(6, "DE151012", "PLATE - DRIVE FOR SPEEDOMETER GEAR", matched_terms=1),
        _row(16, "Dh201079", "SENSOR SPEED-ASSY", matched_terms=2),
    ]
    res = retriever.retrieve("speed sensor")
    assert [h.metadata["part_no"] for h in res.hits] == ["Dh201079", "DE151012"]


def test_vector_search_only_when_no_keyword_hits(fake_db):
    state, calls = fake_db
    state["vector"] = [_row(4, "DJ151041", "AXLE - FRONT", similarity=0.7), SUMMARY]

    res = retriever.retrieve("what holds the front wheel on")

    assert calls["vectors"] == 1
    assert res.lookup_mode == "vector"
    assert [h.id for h in res.hits] == ["28-row-04"]  # summary dropped


def test_no_matches_adds_note(fake_db):
    res = retriever.retrieve("carburettor jet")
    assert res.hits == [] and res.lookup_mode == "vector"
    assert res.notes


def test_whole_assembly_adds_summary_to_keyword_hits(fake_db):
    state, _ = fake_db
    state["keyword"] = [_row(8, "DE151006", "SPACER ASSEMBLY", matched_terms=1)]
    state["vector"] = [SUMMARY]
    res = retriever.retrieve("list all spacer parts")
    assert [h.id for h in res.hits] == ["28-summary", "28-row-08"]
