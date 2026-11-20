"""Offline tests for query_router.py."""

import pytest

from parts_rag.query_router import find_part_codes, route


@pytest.mark.parametrize("query, code", [
    ("Dh201079", "Dh201079"),
    ("what is DH201079?", "DH201079"),
    ("dh201079", "dh201079"),
    ("tell me about 30151033", "30151033"),
    ("LAC00197 qty", "LAC00197"),
    ("is 56DH2Z9L in stock", "56DH2Z9L"),
    ("XX999999", "XX999999"),
])
def test_part_codes(query, code):
    r = route(query)
    assert r.mode == "part_no"
    assert r.value == code  # casing passed through untouched


@pytest.mark.parametrize("query, n", [
    ("part 13", "13"),
    ("item 12", "12"),
    ("Item 7", "7"),
    ("sr no 5", "5"),
    ("Sr. No. 16", "16"),
    ("#13", "13"),
    ("diagram number 3", "3"),
    ("what is part 04?", "4"),
])
def test_sr_no(query, n):
    r = route(query)
    assert r.mode == "sr_no"
    assert r.value == n


@pytest.mark.parametrize("query, terms", [
    ("spacer", ["spacer"]),
    ("sPacer", ["spacer"]),
    ("SPACER", ["spacer"]),
    ("seal", ["seal"]),
    ("disc brake size", ["disc", "brake", "size"]),
])
def test_description(query, terms):
    r = route(query)
    assert r.mode == "description"
    assert r.terms == terms


def test_eight_letter_words_are_not_codes():
    assert find_part_codes("SPACER ASSEMBLY CLEARANCE") == []
    assert route("spacer assembly").mode == "description"


def test_tyre_size_is_not_sr_no():
    assert route("TYRE 80/100-17").mode == "description"


def test_part_code_beats_sr_no():
    r = route("part 13 or DS151058")
    assert r.mode == "part_no" and r.value == "DS151058"


def test_whole_assembly_flag():
    assert route("list all parts in the front wheel assembly").whole_assembly
    assert not route("spacer").whole_assembly
