"""Offline tests for the FastAPI app: retrieval and Claude are faked."""

import pytest
from fastapi.testclient import TestClient

import app as web
from parts_rag.llm import Answer
from parts_rag.query_router import route
from parts_rag.retriever import Hit, Result


def _hit(sr, part, desc, qty=1, source="keyword"):
    return Hit(
        id=f"28-row-{sr:02d}",
        content=f"Sr. No.: {sr} | Part No.: {part} | Description: {desc} | Qty: {qty}",
        metadata={"chunk_type": "row", "sr_no": str(sr), "part_no": part,
                  "description": desc, "qty": qty},
        source=source,
    )


@pytest.fixture
def client():
    return TestClient(web.app)


def fake_retrieve(monkeypatch, hits, mode, notes=()):
    def _retrieve(q):
        return Result(query=q, route=route(q), hits=list(hits), lookup_mode=mode, notes=list(notes))
    monkeypatch.setattr(web.retriever, "retrieve", _retrieve)


def fail_if_llm_called(monkeypatch):
    def _boom(result):
        raise AssertionError("Claude should not be called for this lookup")
    monkeypatch.setattr(web.llm, "answer", _boom)


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "front_wheel_assembly.png" in r.text


def test_ci_fallback_returns_stored_casing(client, monkeypatch):
    fake_retrieve(monkeypatch, [_hit(16, "Dh201079", "SENSOR SPEED-ASSY")], "ci_fallback")
    fail_if_llm_called(monkeypatch)

    data = client.post("/api/search", json={"query": "DH201079"}).json()

    assert data["found"] is True
    assert data["route"] == "part_no" and data["mode"] == "ci_fallback"
    assert data["parts"] == [{"sr_no": 16, "part_no": "Dh201079",
                              "description": "SENSOR SPEED-ASSY", "qty": 1}]
    assert "DH201079" not in data["message"]


def test_sr_no_types(client, monkeypatch):
    fake_retrieve(monkeypatch, [_hit(12, "LAC00197", "BOLT SOCKET STEP M10X1.5", qty=3)], "sr_no")
    fail_if_llm_called(monkeypatch)
    part = client.post("/api/search", json={"query": "item 12"}).json()["parts"][0]
    assert part["sr_no"] == 12 and isinstance(part["sr_no"], int)
    assert part["qty"] == 3


def test_not_found_has_message(client, monkeypatch):
    fake_retrieve(monkeypatch, [], "none", notes=["Part No. 'XX999999' not found."])
    data = client.post("/api/search", json={"query": "XX999999"}).json()
    assert data["found"] is False and data["parts"] == []
    assert data["message"]


def test_vector_hits_filtered_to_parts_claude_names(client, monkeypatch):
    hits = [_hit(3, "56DH2Z9L", "WHEEL FRONT", source="vector"),
            _hit(1, "JF131010", "TYRE 80/100-17", source="vector"),
            _hit(4, "DJ151041", "AXLE - FRONT", source="vector")]
    fake_retrieve(monkeypatch, hits, "vector")
    monkeypatch.setattr(web.llm, "answer", lambda result: Answer(
        text="Part No. DJ151041 - AXLE - FRONT (Sr. No. 4, Qty 1)",
        model="test", casing_ok=True))

    data = client.post("/api/search", json={"query": "what holds the front wheel on"}).json()

    assert data["mode"] == "vector"
    assert [p["part_no"] for p in data["parts"]] == ["DJ151041"]
    assert data["answer"].startswith("Part No. DJ151041")


def test_vector_falls_back_to_closest_when_claude_fails(client, monkeypatch):
    hits = [_hit(4, "DJ151041", "AXLE - FRONT", source="vector"),
            _hit(1, "JF131010", "TYRE 80/100-17", source="vector")]
    fake_retrieve(monkeypatch, hits, "vector")

    def _no_key(result):
        raise RuntimeError("Missing ANTHROPIC_API_KEY")
    monkeypatch.setattr(web.llm, "answer", _no_key)

    data = client.post("/api/search", json={"query": "what holds the front wheel on"}).json()
    assert [p["part_no"] for p in data["parts"]] == ["DJ151041"]
    assert data["answer"] is None and data["message"]


def test_blank_query(client, monkeypatch):
    fail_if_llm_called(monkeypatch)
    data = client.post("/api/search", json={"query": "   "}).json()
    assert data["found"] is False and data["message"]


def test_backend_error_returns_502(client, monkeypatch):
    def _down(q):
        raise ConnectionError("supabase down")
    monkeypatch.setattr(web.retriever, "retrieve", _down)
    r = client.post("/api/search", json={"query": "spacer"})
    assert r.status_code == 502


def test_query_too_long_rejected(client):
    assert client.post("/api/search", json={"query": "x" * 201}).status_code == 422
