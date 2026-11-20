"""End-to-end checks against the live Supabase data.

    python scripts/verify.py              # retrieval checks only (no API cost)
    python scripts/verify.py --with-llm   # also check Claude answers + casing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parts_rag import db  # noqa: E402
from parts_rag.config import DATA_FILE  # noqa: E402
from parts_rag.parser import parse_file  # noqa: E402
from parts_rag.retriever import retrieve  # noqa: E402

SOURCE_PART_NOS = {r.part_no for r in parse_file(DATA_FILE).rows}

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def row_parts(res) -> list[str]:
    return [h.metadata["part_no"] for h in res.rows]


def keyword_parts(res) -> set[str]:
    return {h.metadata["part_no"] for h in res.rows if h.source.startswith("keyword")}


def run_retrieval_checks() -> None:
    print("\nDatabase")
    n = db.count_chunks()
    check("parts_chunks has 17 rows (16 rows + 1 summary)", n == 17, f"got {n}")

    print("\nPart No. lookup (strict first, flexible fallback)")
    r = retrieve("Dh201079")
    check("'Dh201079' -> exact -> Dh201079",
          r.lookup_mode == "exact" and row_parts(r) == ["Dh201079"], f"{r.lookup_mode} {row_parts(r)}")
    for q in ("DH201079", "dh201079"):
        r = retrieve(q)
        check(f"'{q}' -> ci_fallback -> Dh201079 (stored casing)",
              r.lookup_mode == "ci_fallback" and row_parts(r) == ["Dh201079"], f"{r.lookup_mode} {row_parts(r)}")
    r = retrieve("30151033")
    check("'30151033' -> exact -> SEAL - OIL",
          r.lookup_mode == "exact" and r.rows and r.rows[0].metadata["description"] == "SEAL - OIL")
    r = retrieve("XX999999")
    check("'XX999999' -> none, no rows", r.lookup_mode == "none" and not r.rows, f"{r.lookup_mode} {row_parts(r)}")
    r = retrieve("lac00197")
    check("'lac00197' -> ci_fallback -> LAC00197",
          r.lookup_mode == "ci_fallback" and row_parts(r) == ["LAC00197"], f"{r.lookup_mode} {row_parts(r)}")

    print("\nDiagram Sr. No. lookup")
    r = retrieve("part 13")
    check("'part 13' -> DS151058 SPACER",
          r.lookup_mode == "sr_no" and row_parts(r) == ["DS151058"], f"{row_parts(r)}")
    r = retrieve("item 12")
    check("'item 12' -> LAC00197, QTY 3",
          row_parts(r) == ["LAC00197"] and r.rows[0].metadata["qty"] == 3, f"{row_parts(r)}")
    r = retrieve("sr no 16")
    check("'sr no 16' -> Dh201079", row_parts(r) == ["Dh201079"], f"{row_parts(r)}")
    r = retrieve("item 99")
    check("'item 99' -> no rows", not r.rows, f"{row_parts(r)}")

    print("\nCase-insensitive description + semantic search")
    for q in ("spacer", "sPacer", "SPACER"):
        r = retrieve(q)
        check(f"'{q}' -> keyword rows 8 + 13 (DE151006, DS151058) ranked first",
              keyword_parts(r) == {"DE151006", "DS151058"}
              and set(row_parts(r)[:2]) == {"DE151006", "DS151058"},
              f"keyword={sorted(keyword_parts(r))} rows={row_parts(r)}")
    r = retrieve("seal")
    check("'seal' -> keyword rows 5 + 10 (DE151008, 30151033)",
          keyword_parts(r) == {"DE151008", "30151033"}
          and set(row_parts(r)[:2]) == {"DE151008", "30151033"},
          f"keyword={sorted(keyword_parts(r))} rows={row_parts(r)}")
    r = retrieve("disc brake size")
    check("'disc brake size' -> JZ131949 first",
          row_parts(r)[:1] == ["JZ131949"], f"{row_parts(r)}")
    r = retrieve("what holds the front wheel on")
    check("'what holds the front wheel on' -> DJ151041 AXLE in top 3",
          "DJ151041" in row_parts(r)[:3], f"{row_parts(r)}")
    r = retrieve("speed sensor")
    check("'speed sensor' -> Dh201079 first", row_parts(r)[:1] == ["Dh201079"], f"{row_parts(r)}")
    r = retrieve("list all parts in the front wheel assembly")
    check("whole-assembly question includes the summary chunk",
          any(h.id == "28-summary" for h in r.hits), f"{[h.id for h in r.hits]}")

    print("\nCasing integrity")
    stored = {h.metadata["part_no"] for h in retrieve("Dh201079").rows}
    check("stored part_no is 'Dh201079' (not uppercased)", stored == {"Dh201079"}, f"{stored}")
    all_hits = [h for q in ("seal", "spacer", "DH201079", "part 13") for h in retrieve(q).rows]
    bad = {h.metadata["part_no"] for h in all_hits} - SOURCE_PART_NOS
    check("every returned part_no matches the source file exactly", not bad, f"{bad}")


def run_llm_checks() -> None:
    from parts_rag.llm import answer

    print("\nClaude answers (casing check on every reply)")
    cases = [
        ("DH201079", ["Dh201079"]),
        ("dh201079", ["Dh201079"]),
        ("part 13", ["DS151058"]),
        ("item 12", ["LAC00197"]),
        ("spacer", ["DE151006", "DS151058"]),
        ("seal", ["DE151008", "30151033"]),
        ("XX999999", []),
    ]
    for q, must_have in cases:
        res = retrieve(q)
        ans = answer(res)
        missing = [p for p in must_have if p not in ans.text]
        check(f"'{q}' -> answer has {must_have or 'no part numbers'} verbatim, casing OK",
              ans.casing_ok and not missing,
              f"missing={missing} unknown={ans.unknown_codes}\n        answer: {ans.text[:300]!r}")
    res = retrieve("DH201079")
    ans = answer(res)
    check("answer to 'DH201079' never writes 'DH201079'", "DH201079" not in ans.text, repr(ans.text[:300]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-llm", action="store_true", help="also call Claude (uses API credits)")
    args = ap.parse_args()

    run_retrieval_checks()
    if args.with_llm:
        run_llm_checks()

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
