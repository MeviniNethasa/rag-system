"""Offline tests for parser.py and chunker.py (no network, no keys)."""

import pytest

from parts_rag.chunker import build_chunks
from parts_rag.config import DATA_FILE
from parts_rag.parser import ParseError, parse_file, parse_text


@pytest.fixture(scope="module")
def assembly():
    return parse_file(DATA_FILE)


def test_header_fields(assembly):
    assert assembly.model == "Pulsar N-125"
    assert assembly.model_code == "00JZF7ZZ"
    assert assembly.assembly_no == "28"
    assert assembly.assembly_name == "Front Wheel Assembly - Disc Brake"


def test_sixteen_rows_in_order(assembly):
    assert [r.sr_no for r in assembly.rows] == [str(i) for i in range(1, 17)]


def test_part_no_casing_preserved(assembly):
    last = assembly.rows[15]
    assert last.part_no == "Dh201079"
    assert last.part_no != "DH201079"


def test_every_part_no_matches_source_text_exactly(assembly):
    raw = DATA_FILE.read_text(encoding="utf-8")
    for row in assembly.rows:
        assert f"| {row.part_no} |" in raw


def test_specific_rows(assembly):
    by_sr = {r.sr_no: r for r in assembly.rows}
    assert by_sr["12"].part_no == "LAC00197"
    assert by_sr["12"].qty == 3
    assert by_sr["13"].description == "SPACER"
    assert by_sr["3"].description == "WHEEL FRONT 1.85X17(JZ131064) MAT C BLK"
    assert all(r.remark == "" for r in assembly.rows)


def test_rejects_duplicate_part_no():
    text = (
        "Model: X (ABC)\nAssembly: 1. Test\n"
        "Sr. No. | Part No. | Description | QTY. | Remark\n"
        "1 | AA000001 | ONE | 1 |\n2 | AA000001 | TWO | 1 |\n"
    )
    with pytest.raises(ParseError, match="Duplicate"):
        parse_text(text, expected_rows=2)


def test_rejects_wrong_row_count():
    text = (
        "Model: X (ABC)\nAssembly: 1. Test\n"
        "Sr. No. | Part No. | Description | QTY. | Remark\n"
        "1 | AA000001 | ONE | 1 |\n"
    )
    with pytest.raises(ParseError, match="Expected 16 rows"):
        parse_text(text)


def test_chunks(assembly):
    chunks = build_chunks(assembly)
    assert len(chunks) == 17
    ids = [c.id for c in chunks]
    assert ids[0] == "28-row-01" and ids[15] == "28-row-16" and ids[16] == "28-summary"
    assert len(set(ids)) == 17

    sensor = chunks[15]
    assert sensor.metadata["part_no"] == "Dh201079"
    assert sensor.metadata["sr_no"] == "16"
    assert sensor.metadata["chunk_type"] == "row"
    assert "Part No.: Dh201079" in sensor.content
    assert "DH201079" not in sensor.content

    summary = chunks[16]
    assert summary.metadata["chunk_type"] == "summary"
    assert "Dh201079" in summary.content
    assert summary.content.count("Sr. No. ") == 16
